from __future__ import annotations

from knowledge.sector_narrative_alias import build_sector_driver_tag_profile

__all__ = ["build_realtime_tag_evidence_snapshot", "format_tag_evidence_snapshot_for_context"]


CHIP_BRANCH_MARKERS = ("国产芯片", "国产替代", "芯片替代")
CONTRADICTION_MARKERS = ("尚未", "未达成", "没有合作", "无合作", "业务占比小", "暂未", "未形成收入", "未产生利润", "传闻不实")
AI_COMPUTE_MARKERS = ("数据中心", "液冷服务器", "算力", "英伟达概念", "服务器", "AIDC", "东数西算", "云计算")
CONSUMER_ELECTRONICS_MARKERS = ("消费电子", "苹果概念", "AI眼镜", "AI PC", "智能穿戴", "无线耳机", "3D摄像头", "OLED", "柔性屏", "MR", "VR", "AR")


def _clean_text(value) -> str:
    try:
        if value != value:
            return ""
    except Exception:
        pass
    text = str(value or "").strip()
    return "" if text.lower() == "nan" else text


def _split_terms(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        terms = []
        for key, item in value.items():
            terms.append(key)
            terms.extend(_split_terms(item))
        return [term for term in terms if term]
    if isinstance(value, (list, tuple, set)):
        terms = []
        for item in value:
            terms.extend(_split_terms(item))
        return [term for term in terms if term]
    text = _clean_text(value)
    if not text:
        return []
    for marker in (";", "；", "、", "|", "/", "，"):
        text = text.replace(marker, ",")
    return [_clean_text(part) for part in text.split(",") if _clean_text(part)]


def _append_unique(target, values):
    for value in _split_terms(values):
        if value and value not in target:
            target.append(value)


def _iter_named_rows(value):
    if isinstance(value, dict):
        for key, row in value.items():
            if isinstance(row, dict):
                merged = dict(row)
                merged.setdefault("name", key)
                yield merged
            else:
                yield {"name": key, "value": row}
        return
    for row in value or []:
        if isinstance(row, dict):
            yield row


def _collect_tag_terms(data) -> dict:
    data = data or {}
    funds = []
    attention = []
    labels = []
    risks = []

    for bucket_name in ("sector_fund_flow", "concept_fund_flow"):
        bucket = data.get(bucket_name) or {}
        if isinstance(bucket, dict):
            for side in ("inflow", "outflow", "rows", "items"):
                for row in bucket.get(side, []) or []:
                    name = _clean_text((row or {}).get("name") or (row or {}).get("sector_name"))
                    if name:
                        funds.append(name)
        elif isinstance(bucket, list):
            for row in bucket:
                name = _clean_text((row or {}).get("name") or (row or {}).get("sector_name"))
                if name:
                    funds.append(name)

    for row in data.get("hot_plates", []) or []:
        _append_unique(attention, (row or {}).get("name"))

    for row in data.get("hot_rank_top30", []) or []:
        _append_unique(attention, (row or {}).get("sector"))
        _append_unique(attention, (row or {}).get("concepts"))
        _append_unique(attention, (row or {}).get("reason"))

    for row in data.get("integrated_hot_list", []) or []:
        _append_unique(attention, (row or {}).get("sector"))
        _append_unique(attention, (row or {}).get("concepts"))
        _append_unique(attention, (row or {}).get("reason"))

    for row in data.get("xueqiu_hot_stock_arguments", []) or []:
        _append_unique(attention, (row or {}).get("argument") or (row or {}).get("reason") or (row or {}).get("summary"))

    for key in ("eastmoney_label_rows", "eastmoney_labels", "security_code_labels"):
        for row in _iter_named_rows(data.get(key)):
            _append_unique(labels, (row or {}).get("labels") or (row or {}).get("label") or (row or {}).get("concepts"))

    for row in _iter_named_rows(data.get("stock_risk_map")):
        text = _clean_text((row or {}).get("risk_summary") or (row or {}).get("reason"))
        if text:
            risks.append(text)

    return {"funds": funds, "attention": attention, "labels": labels, "risks": risks}


def _contains_any(text, markers) -> bool:
    return any(marker in text for marker in markers)


def _has_chip_substitution(text) -> bool:
    return _contains_any(text, CHIP_BRANCH_MARKERS)


def _dedupe(values) -> list[str]:
    result = []
    for value in values or []:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _terms_text(terms) -> str:
    return " ".join(_split_terms(terms))


def _risk_text(risks) -> str:
    matched = []
    for risk in risks or []:
        text = _clean_text(risk)
        if text and _contains_any(text, CONTRADICTION_MARKERS):
            matched.append(text)
    return "；".join(matched[:2])


def _build_group(adopted, family, branch, surface, *, relation, funds, attention, auxiliary=None, risk_text=""):
    auxiliary = _dedupe(auxiliary or [])
    reasons = []
    if relation == "证据不足":
        reasons.append("没有细分分支证据")
    if risk_text:
        reasons.append("存在反证信息")
    return {
        "采用名称": adopted,
        "大方向": family,
        "当日主攻分支": branch,
        "表层行业名": _dedupe(surface),
        "辅助名称": auxiliary,
        "噪音名称": [],
        "反证信息": risk_text,
        "资金证据": "资金指向：" + " / ".join(_dedupe(funds)[:5]) if funds else "",
        "注意力证据": "热榜/雪球指向：" + " / ".join(_dedupe(attention)[:5]) if attention else "",
        "扩散证据": "",
        "关系判断": relation,
        "未采用名称及原因": "；".join(reasons),
    }


def _choose_hard_tech_group(terms, funds, attention, risks):
    text = _terms_text(terms)
    profile = build_sector_driver_tag_profile(terms)
    branches = list(profile.get("driver_branches") or [])
    hard_branches = {
        "光通信/CPO",
        "存储/芯片",
        "PCB/电子材料",
        "被动元件/MLCC",
    }
    surface = [
        term
        for term in _split_terms(terms)
        if any(marker in term for marker in ("半导体", "芯片", "元器件", "元件", "电子元件", "电子元器件"))
    ]
    if _has_chip_substitution(text):
        branch = "国产芯片替代"
        adopted = branch
        if branch not in branches:
            branches.insert(0, branch)
    elif any(branch_item in hard_branches for branch_item in branches):
        branch = next(branch_item for branch_item in branches if branch_item in hard_branches)
        adopted = branch
    else:
        branch = ""
        adopted = surface[0] if surface else ""
    if not adopted:
        return None
    family = "泛半导体/硬科技电子" if branch else ""
    relation = "父子" if branch else "证据不足"
    return _build_group(
        adopted,
        family,
        branch,
        surface or [adopted],
        relation=relation,
        funds=funds,
        attention=attention,
        auxiliary=[item for item in branches if item != branch] + [term for term in _split_terms(terms) if term in ("PCB", "CPO", "MLCC")],
        risk_text=_risk_text(risks),
    )


def _matched_family_surface_terms(adopted, terms) -> list[str]:
    source_terms = _split_terms(terms)
    marker_map = {
        "AI算力基础设施": AI_COMPUTE_MARKERS,
        "AI终端/消费电子": CONSUMER_ELECTRONICS_MARKERS,
    }
    markers = marker_map.get(adopted)
    if not markers:
        return source_terms
    matched = []
    for term in source_terms:
        if term == adopted or _contains_any(term, markers):
            matched.append(term)
    return _dedupe(matched) or [adopted]


def _build_family_group(adopted, terms, funds, attention, risks):
    profile = build_sector_driver_tag_profile(terms)
    surface = _matched_family_surface_terms(adopted, profile.get("surface_tags") or _split_terms(terms))
    return _build_group(
        adopted,
        adopted,
        adopted,
        surface,
        relation="分支",
        funds=funds,
        attention=attention,
        risk_text=_risk_text(risks),
    )


def build_realtime_tag_evidence_snapshot(data) -> dict:
    collected = _collect_tag_terms(data)
    all_terms = _dedupe(collected["funds"] + collected["attention"] + collected["labels"])
    text = _terms_text(all_terms)
    groups = []

    hard_group = _choose_hard_tech_group(all_terms, collected["funds"], collected["attention"], collected["risks"])
    if hard_group:
        groups.append(hard_group)

    profile = build_sector_driver_tag_profile(all_terms)
    family = profile.get("family", "")
    if family == "AI终端/消费电子" and not any(group["采用名称"] == "AI终端/消费电子" for group in groups):
        groups.append(_build_family_group("AI终端/消费电子", all_terms, collected["funds"], collected["attention"], collected["risks"]))
    if _contains_any(text, AI_COMPUTE_MARKERS) and not any(
        group["采用名称"] == "AI算力基础设施" for group in groups
    ):
        groups.append(_build_family_group("AI算力基础设施", all_terms, collected["funds"], collected["attention"], collected["risks"]))

    if not groups and all_terms:
        groups.append(
            _build_group(
                all_terms[0],
                "",
                "",
                [all_terms[0]],
                relation="证据不足",
                funds=collected["funds"],
                attention=collected["attention"],
                risk_text=_risk_text(collected["risks"]),
            )
        )

    adopted_labels = [group["采用名称"] for group in groups if group.get("采用名称")]
    summary_parts = [f"采用名称：{group['采用名称']}" for group in groups[:3] if group.get("采用名称")]
    if len(groups) >= 2:
        summary_parts.append("多分支关系")
    return {
        "groups": groups,
        "adopted_labels": adopted_labels,
        "summary_text": "；".join(summary_parts),
    }


def format_tag_evidence_snapshot_for_context(snapshot) -> str:
    groups = list((snapshot or {}).get("groups") or [])
    if not groups:
        return ""
    lines = ["实时tag证据快照："]
    for group in groups[:5]:
        parts = [
            f"采用名称：{group.get('采用名称', '')}",
            f"大方向：{group.get('大方向', '')}",
            f"当日主攻分支：{group.get('当日主攻分支', '')}",
            f"表层行业名：{' / '.join(group.get('表层行业名') or [])}",
            f"关系判断：{group.get('关系判断', '')}",
        ]
        reason = _clean_text(group.get("未采用名称及原因"))
        if reason:
            parts.append(f"未采用名称及原因：{reason}")
        lines.append("；".join(part for part in parts if part and not part.endswith("：")))
    return "\n".join(lines)
