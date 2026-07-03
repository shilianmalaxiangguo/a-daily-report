from __future__ import annotations

from typing import Mapping

from report.surface_wording import sanitize_user_visible_text


SCHEMA_VERSION = "bayesian_diagnosis.v1"
SOURCE_DATE_MISSING = "来源日期缺失"
PATH_LAYERS = ("market", "mainline", "capital", "stock", "counter_evidence")


def _as_dict(value):
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value):
    return list(value) if isinstance(value, list) else []


def _clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    text = sanitize_user_visible_text(text)
    return text if text else default


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace("%", "").strip() or default))
    except (TypeError, ValueError):
        return default


def _normalize_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _stock_payload(value):
    if not isinstance(value, Mapping):
        return {}
    code = _normalize_code(value.get("code") or value.get("stock_code") or value.get("symbol") or value.get("代码"))
    name = _clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    if not (code or name):
        return {}
    payload = {"code": code, "name": name}
    for key, aliases in {
        "sector": ("sector", "sector_name", "industry", "板块", "所属板块"),
        "role": ("role", "candidate_role", "quality_role", "target_role", "sniper_role"),
        "source_date": ("source_date", "trade_date", "query_date", "date"),
    }.items():
        text = _clean_text(next((value.get(alias) for alias in aliases if value.get(alias) not in (None, "")), ""))
        if text:
            payload[key] = text
    return payload


def _same_stock(left, right):
    left_payload = _stock_payload(left)
    right_payload = _stock_payload(right)
    if left_payload.get("code") and right_payload.get("code"):
        return left_payload["code"] == right_payload["code"]
    return bool(left_payload.get("name") and left_payload.get("name") == right_payload.get("name"))


def _first_stock(*values):
    for value in values:
        payload = _stock_payload(value)
        if payload:
            return payload
    return {}


def _source_date(*values):
    for value in values:
        if not isinstance(value, Mapping):
            continue
        text = _clean_text(value.get("source_date") or value.get("trade_date") or value.get("query_date") or value.get("date"))
        if text:
            return text
    return SOURCE_DATE_MISSING


def _step(*, source_date, layer, input_summary, judgement, passes_forward, cannot_conclude=None, conflicts=None):
    return {
        "source_date": _clean_text(source_date, SOURCE_DATE_MISSING),
        "layer": _clean_text(layer),
        "input_summary": _clean_text(input_summary, "无输入摘要"),
        "judgement": _clean_text(judgement, "条件待确认"),
        "passes_forward": _clean_text(passes_forward, "待确认"),
        "cannot_conclude": [_clean_text(item) for item in list(cannot_conclude or []) if _clean_text(item)],
        "conflicts": [_clean_text(item) for item in list(conflicts or []) if _clean_text(item)],
    }


def _selection_workflow_final(*sources):
    for source in sources:
        workflow = _as_dict(_as_dict(source).get("selection_workflow"))
        if workflow.get("schema_version") != "selection_workflow.v1":
            continue
        final = _as_dict(workflow.get("final"))
        if final:
            return final
    return {}


def _capital_priority(final_target_resolution):
    resolution = _as_dict(final_target_resolution)
    decision = _as_dict(resolution.get("capital_priority_decision"))
    return _clean_text(decision.get("capital_priority") or resolution.get("capital_priority") or resolution.get("priority"))


def _resolution_target(final_target_resolution):
    resolution = _as_dict(final_target_resolution)
    priority = _capital_priority(resolution)
    if priority in {"wait", "old_position_t", "old_position", "existing_position", "existing_position_t"}:
        return _first_stock(resolution.get("watch_target"), resolution.get("display_target"), resolution.get("process_target"))
    if priority in {"tradable_proxy", "proxy", "proxy_target"}:
        return _first_stock(resolution.get("display_target"), resolution.get("tradable_proxy_target"), resolution.get("watch_target"))
    return _first_stock(resolution.get("display_target"), resolution.get("new_entry_target"), resolution.get("watch_target"), resolution.get("process_target"))


def _final_action_context(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    position_decision=None,
):
    final = _selection_workflow_final(data, execution_stage_context, market_research_snapshot)
    if final:
        position_pct = _safe_int(final.get("position_pct"))
        target = _stock_payload(final.get("execution_object"))
        return {
            "source": "selection_workflow.final",
            "position_pct": position_pct,
            "execution_object": target if position_pct > 0 else {},
            "action_text": _clean_text(
                final.get("action_text"),
                "0%不参与" if position_pct <= 0 else "已决定按条件参与；不满足回到0%不参与",
            ),
        }
    decision = _as_dict(position_decision)
    position_pct = _safe_int(decision.get("target_position_pct") or decision.get("position_pct"))
    target = _resolution_target(final_target_resolution)
    if position_pct <= 0:
        target = {}
    action_text = _clean_text(
        decision.get("final_action") or decision.get("sizing_reason"),
        "0%不参与" if position_pct <= 0 else "已决定按条件参与；不满足回到0%不参与",
    )
    if position_pct == 50 and ("50%条件执行" not in action_text or "回到0" not in action_text):
        action_text = "已决定50%条件执行；盘中不满足取消，回到0%不参与"
    return {
        "source": "final_target_resolution",
        "position_pct": position_pct,
        "execution_object": target,
        "action_text": action_text,
    }


def _market_step(target_date, data, market_research_snapshot):
    market = _as_dict(market_research_snapshot.get("market_structure_judgement") or data.get("market_structure_judgement"))
    market_state = _clean_text(
        market.get("market_background")
        or market.get("tomorrow_rhythm")
        or market.get("market_state")
        or market_research_snapshot.get("market_branch")
        or data.get("market_branch"),
        "市场状态待确认",
    )
    source_date = _source_date(market, market_research_snapshot, data)
    return _step(
        source_date=source_date,
        layer="market",
        input_summary=market_state,
        judgement="市场未否定继续诊断" if market_state != "市场状态待确认" else "市场层信息待确认",
        passes_forward="进入主线层" if market_state != "市场状态待确认" else "不能单独推出参与资格",
        cannot_conclude=["市场层不能直接推出个股"],
    )


def _mainline_step(target_date, data, market_research_snapshot):
    mainline = _as_dict(market_research_snapshot.get("cycle_layer") or data.get("cycle_layer"))
    daily = _clean_text(
        mainline.get("daily_attack_line")
        or mainline.get("daily")
        or market_research_snapshot.get("daily_attack_line")
        or data.get("daily_attack_line"),
    )
    cycle = _clean_text(
        mainline.get("cycle_mainline")
        or mainline.get("mainline")
        or market_research_snapshot.get("cycle_mainline")
        or data.get("cycle_mainline"),
    )
    summary = "；".join(text for text in (cycle, daily) if text) or "主线信息待确认"
    source_date = _source_date(mainline, market_research_snapshot, data)
    return _step(
        source_date=source_date,
        layer="mainline",
        input_summary=summary,
        judgement="主线允许继续诊断" if summary != "主线信息待确认" else "主线层信息待确认",
        passes_forward="进入资金层" if summary != "主线信息待确认" else "不能单独推出参与资格",
        cannot_conclude=["主线层不能替代个股参与资格"],
    )


def _capital_step(target_date, data, market_research_snapshot, final_target_resolution, final_action):
    capital = _as_dict(market_research_snapshot.get("capital_intent") or data.get("capital_intent"))
    priority = _capital_priority(final_target_resolution)
    summary = _clean_text(
        capital.get("summary")
        or capital.get("capital_summary")
        or _as_dict(final_target_resolution).get("capital_priority_decision", {}).get("reason"),
        "资金层信息待确认",
    )
    source_date = _source_date(capital, final_action.get("execution_object"), market_research_snapshot, data)
    cannot_conclude = ["资金层不能替代固定交易窗口"]
    if priority in {"old_position_t", "old_position", "existing_position", "existing_position_t"}:
        cannot_conclude.append("旧仓优先时不能把新机会写成直接参与")
    return _step(
        source_date=source_date,
        layer="capital",
        input_summary=summary,
        judgement="资金未否定最终动作" if summary != "资金层信息待确认" else "资金层信息待确认",
        passes_forward="进入个股层" if summary != "资金层信息待确认" else "只能继续观察",
        cannot_conclude=cannot_conclude,
    )


def _stock_step(target_date, final_action, position_decision):
    target = final_action.get("execution_object") if isinstance(final_action.get("execution_object"), dict) else {}
    source_date = _source_date(target, position_decision or {})
    position_pct = _safe_int(final_action.get("position_pct"))
    if not target or position_pct <= 0:
        return _step(
            source_date=source_date,
            layer="stock",
            input_summary="无明日执行对象",
            judgement="没有形成参与资格",
            passes_forward="不新增参与",
            cannot_conclude=["观察对象不能写成参与对象"],
        )
    label = _clean_text(target.get("name") or target.get("code"), "执行对象")
    return _step(
        source_date=source_date,
        layer="stock",
        input_summary=f"{label}进入最终动作复核",
        judgement="个股具备最终动作承接",
        passes_forward="进入反证复核",
        cannot_conclude=["个股强度不能取消固定交易窗口"],
    )


def _counter_evidence(data, market_research_snapshot, final_target_resolution, position_decision):
    evidence = []
    for source in (data, market_research_snapshot, final_target_resolution, position_decision):
        source = _as_dict(source)
        for key in ("counter_evidence", "risk_points", "failure_conditions", "cancellation_conditions", "missing_fields"):
            value = source.get(key)
            if isinstance(value, str):
                value = [value]
            if isinstance(value, list):
                evidence.extend(_clean_text(item) for item in value if _clean_text(item))
    return list(dict.fromkeys(evidence))


def _counter_step(target_date, data, market_research_snapshot, final_target_resolution, position_decision, counter_evidence):
    source_date = _source_date(final_target_resolution, position_decision or {}, market_research_snapshot, data)
    if counter_evidence:
        summary = "；".join(counter_evidence[:3])
        judgement = "存在反证，不能放大动作"
        passes_forward = "保留为复核提示"
    else:
        summary = "暂无强反证"
        judgement = "未发现强反证"
        passes_forward = "维持当前最终动作"
    return _step(
        source_date=source_date,
        layer="counter_evidence",
        input_summary=summary,
        judgement=judgement,
        passes_forward=passes_forward,
        cannot_conclude=["反证层只能降低或提示风险，不能创造新对象"],
    )


def _path_conclusion(final_action, path, counter_evidence):
    position_pct = _safe_int(final_action.get("position_pct"))
    target = final_action.get("execution_object") if isinstance(final_action.get("execution_object"), dict) else {}
    has_missing_date = any(_clean_text(step.get("source_date")) == SOURCE_DATE_MISSING for step in path if isinstance(step, dict))
    if not target or position_pct <= 0:
        return "无执行对象"
    if counter_evidence:
        return "存在反证"
    if has_missing_date:
        return "路径不完整，条件待确认"
    if position_pct >= 100:
        return "路径一致"
    if position_pct >= 50:
        return "条件执行"
    return "路径不完整，条件待确认"


def build_bayesian_diagnosis_packet(
    *,
    target_date="",
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    position_decision=None,
):
    data = _as_dict(data)
    execution_stage_context = _as_dict(execution_stage_context)
    market_research_snapshot = _as_dict(market_research_snapshot)
    final_target_resolution = _as_dict(
        final_target_resolution
        or data.get("final_target_resolution")
        or execution_stage_context.get("final_target_resolution")
        or market_research_snapshot.get("final_target_resolution")
    )
    position_decision = _as_dict(
        position_decision
        or data.get("position_decision")
        or execution_stage_context.get("position_decision")
        or market_research_snapshot.get("position_decision")
    )
    target_date = _clean_text(
        target_date
        or data.get("target_date")
        or execution_stage_context.get("target_date")
        or market_research_snapshot.get("target_date")
    )
    final_action = _final_action_context(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
    )
    counter_evidence = _counter_evidence(data, market_research_snapshot, final_target_resolution, position_decision)
    path = [
        _market_step(target_date, data, market_research_snapshot),
        _mainline_step(target_date, data, market_research_snapshot),
        _capital_step(target_date, data, market_research_snapshot, final_target_resolution, final_action),
        _stock_step(target_date, final_action, position_decision),
        _counter_step(target_date, data, market_research_snapshot, final_target_resolution, position_decision, counter_evidence),
    ]
    path_conclusion = _path_conclusion(final_action, path, counter_evidence)
    execution_object = final_action.get("execution_object") if isinstance(final_action.get("execution_object"), dict) else {}
    conclusion = {
        "path_conclusion": path_conclusion,
        "execution_object": dict(execution_object),
        "position_pct": _safe_int(final_action.get("position_pct")),
        "action_text": _clean_text(final_action.get("action_text")),
        "final_action_alignment": "一致",
        "final_action_source": _clean_text(final_action.get("source")),
    }
    if counter_evidence and path_conclusion == "路径一致":
        conclusion["path_conclusion"] = "存在反证"
    return {
        "schema_version": SCHEMA_VERSION,
        "target_date": target_date,
        "conclusion": conclusion,
        "path": path,
        "counter_evidence": counter_evidence,
        "conflicts": [],
        "path_layers": list(PATH_LAYERS),
    }
