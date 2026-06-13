from report.surface_wording import sanitize_user_visible_text
from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    blocked_current_observation_keys,
    candidate_can_be_current_observation_target,
)


def _candidate_key(candidate):
    candidate = candidate or {}
    return str(candidate.get("code") or candidate.get("stock_code") or candidate.get("代码") or candidate.get("name") or candidate.get("名称") or "").strip()


def _preferred_observation_target(context):
    for key in ("front_page_selected_position_candidate", "selected_position_candidate"):
        candidate = context.get(key)
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    for candidate in context.get("extreme_conviction_list", []) or []:
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    step2_bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    for candidate in step2_bundle.get("extreme_conviction_list", []) or []:
        if isinstance(candidate, dict) and _candidate_key(candidate):
            return candidate
    return None


def _prioritize_final_observation_anchor(context, candidates):
    target = _preferred_observation_target(context)
    target_key = _candidate_key(target)
    if not target_key:
        return list(candidates or [])
    matched = []
    remaining = []
    for candidate in list(candidates or []):
        if _candidate_key(candidate) == target_key:
            matched.append(candidate)
        else:
            remaining.append(candidate)
    if matched:
        return matched + remaining
    return [target] + remaining


def _surface_observation_candidates(candidates):
    return [
        candidate
        for candidate in list(candidates or [])
        if candidate_can_be_current_observation_target(candidate)
    ]


def _position_pct(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _candidate_with_workflow_identity(candidate):
    candidate = candidate if isinstance(candidate, dict) else {}
    stock = candidate.get("stock") if isinstance(candidate.get("stock"), dict) else candidate
    payload = dict(stock or {})
    for key, value in candidate.items():
        if key == "stock":
            continue
        if payload.get(key) in (None, "") and value not in (None, ""):
            payload[key] = value
    return payload


def _selection_workflow_from_context(context):
    sources = [context]
    if isinstance(context, dict):
        sources.extend([context.get("market_research_snapshot"), context.get("execution_stage_context")])
    for source in sources:
        if not isinstance(source, dict):
            continue
        workflow = source.get("selection_workflow")
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _selection_workflow_front_observation_target(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    for candidate in workflow.get("candidate_pool", []) or []:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("front_observation_qualified") is not True:
            continue
        payload = _candidate_with_workflow_identity(candidate)
        if candidate_can_be_current_observation_target(payload):
            return payload
    return {}


def _final_resolution_watch_target(context):
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return {}
    watch_target = resolution.get("watch_target")
    return watch_target if candidate_can_be_current_observation_target(watch_target) else {}


def _final_resolution_waits_without_watch_target(context):
    resolution = (context or {}).get("final_target_resolution")
    if not isinstance(resolution, dict):
        return False
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    if str(decision.get("capital_priority") or "").strip() != "wait":
        return False
    return not bool(_final_resolution_watch_target(context))


def _final_target_empty_without_current_observation(context):
    workflow = _selection_workflow_from_context(context)
    if workflow:
        final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
        if "final" in workflow:
            execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
            position_pct = _position_pct(final.get("position_pct"))
            if position_pct <= 0 or not _candidate_key(execution_object):
                return True
    if _final_resolution_waits_without_watch_target(context):
        return True
    if _final_resolution_watch_target(context):
        return False
    if not workflow:
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if "final" not in workflow:
        return False
    execution_object = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    position_pct = _position_pct(final.get("position_pct"))
    if position_pct > 0 and _candidate_key(execution_object):
        return False
    return not bool(_selection_workflow_front_observation_target(workflow))


def _is_ten_confirm_upgrade_candidate(candidate):
    candidate = candidate or {}
    text = " ".join(
        str(candidate.get(key, "") or "")
        for key in (
            "permission_label",
            "watch_anchor_type",
            "conviction_reason",
            "reason",
            "core_level",
            "watch_anchor_note",
        )
    )
    minute_plan = candidate.get("minute_plan") or {}
    return bool(
        minute_plan.get("confirm_price_60m")
        and (
            any(marker in text for marker in ("重点观察名单", "重点观察权", "重点观察确认"))
            or "极看" in text
            or "极度看好" in text
            or "板块锚定龙" in text
            or "首波先锋" in text
            or "主线核心" in text
        )
    )


def build_pk_decision_pk_context_node(context, node_meta=None, node_lookup=None):
    trade_gate_open = context.get("trade_gate_open", False)
    display_pending_candidates = context.get("display_pending_candidates", context.get("pending_candidates", [])) or []
    display_observation_candidates = context.get("display_observation_candidates", context.get("observation_candidates", [])) or []
    display_observation_candidates = _prioritize_final_observation_anchor(context, display_observation_candidates)
    blocked_observation_keys = blocked_current_observation_keys(display_observation_candidates)
    display_observation_candidates = _surface_observation_candidates(display_observation_candidates)
    best_stock = context.get("best_stock")
    watch_anchor = context.get("watch_anchor")
    if not candidate_can_be_current_observation_target(watch_anchor) or _candidate_key(watch_anchor) in blocked_observation_keys:
        watch_anchor = None
    if _final_target_empty_without_current_observation(context):
        display_pending_candidates = []
        display_observation_candidates = []
        best_stock = None
        watch_anchor = None
    watch_anchor_type = context.get("watch_anchor_type", "")
    position_level = str(context.get("position_level", "") or "").strip()
    final_gate = context.get("final_gate", {}) or {}
    front_structure_layer_text = context.get("front_structure_layer_text", "")

    safe_float = context.get("safe_float", lambda value, default=0.0: float(default if value in (None, "") else value))
    build_trade_price_focus = context.get("build_trade_price_focus", lambda minute_plan, stop_plan: {})
    build_observation_price_focus_text = context.get("build_observation_price_focus_text", lambda price_focus: "-")
    should_surface_price_note = context.get("should_surface_price_note", lambda price_focus: False)
    build_observation_price_note_text = context.get("build_observation_price_note_text", lambda price_focus: "-")
    append_watch_anchor_note = context.get("append_watch_anchor_note", lambda report_lines, candidate, prefix="  ": None)
    compose_observation_focus_text = context.get(
        "compose_observation_focus_text",
        lambda confirm_text, observation_price_focus_text: f"{confirm_text} / {observation_price_focus_text}",
    )
    build_stop_execution_plan = context.get("build_stop_execution_plan", lambda *args, **kwargs: {})
    observation_anchor = display_observation_candidates[0] if display_observation_candidates else watch_anchor
    watch_anchor_for_upgrade = dict(observation_anchor or watch_anchor or {})
    if watch_anchor_type and "watch_anchor_type" not in watch_anchor_for_upgrade:
        watch_anchor_for_upgrade["watch_anchor_type"] = watch_anchor_type
    ten_confirm_upgrade_candidate = next(
        (candidate for candidate in [watch_anchor_for_upgrade] + list(display_observation_candidates) if _is_ten_confirm_upgrade_candidate(candidate)),
        None,
    )

    pending_lines = []
    if trade_gate_open:
        if display_pending_candidates:
            if len(display_pending_candidates) >= 2:
                pending_lines.append(f"**重点盯盘股排序**（{len(display_pending_candidates)}只，先看谁最可能走成明天唯一能买的那只）:")
                pending_lines.append("| 股票 | 来源 | 09:50-10:10观察价 | 候选顺位 | 说明 |")
                pending_lines.append("|------|------|--------------|----------|------|")
                for idx, candidate in enumerate(display_pending_candidates[:5], 1):
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    source_text = candidate.get("permission_label", "候选")
                    note = candidate.get("reason", candidate.get("permission_reason", "等待盘中确认"))
                    pending_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                pending_lines.append("")
            top_pending = display_pending_candidates[0]
            top_minute_plan = top_pending.get("minute_plan") or {}
            top_stop_plan = top_pending.get("stop_plan")
            top_price_focus = build_trade_price_focus(top_minute_plan, top_stop_plan)
            top_confirm_price = top_minute_plan.get("confirm_price_60m")
            top_price_focus_text = build_observation_price_focus_text(top_price_focus)
            pending_lines.append(f"**明天先盯哪只**: {top_pending.get('name')}({top_pending.get('code')})")
            pending_lines.append(
                f"- **原因**: {top_pending.get('permission_reason', top_pending.get('reason', '当前先看它能否继续证明自己'))}"
            )
            if top_confirm_price:
                pending_lines.append(f"- **09:50-10:10观察价**: {top_confirm_price:.2f}")
            if top_price_focus_text and top_price_focus_text != "-":
                pending_lines.append(f"- **价格怎么盯**: {top_price_focus_text}")
            if should_surface_price_note(top_price_focus):
                pending_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(top_price_focus)}")
            pending_lines.append("- **升级条件**: 明日先09:50-10:10窗口满足条件，再走成明天唯一能买的那只，不能直接追价")
            pending_lines.append("")
        else:
            pending_lines.extend(["**当前没有能下手的票**: 无需PK", ""])

    observation_lines = []
    if not trade_gate_open:
        if display_observation_candidates:
            if len(display_observation_candidates) >= 2:
                observation_lines.append(f"**先看谁排第几**（{len(display_observation_candidates)}只，优先盯强分歧但没坏的对象）:")
                observation_lines.append("| 股票 | 来源 | 买点 | 09:50-10:10观察价 | 先看顺序 | 说明 |")
                observation_lines.append("|------|------|------|--------------|------------|------|")
                source_label_map = {
                    "execute_layer": "执行层",
                    "keep_group_watch": "观察组",
                    "waiting_layer": "等待层",
                    "abnormal_probe": "异常层",
                }
                for idx, candidate in enumerate(display_observation_candidates[:5], 1):
                    signal = candidate.get("signal")
                    minute_plan = candidate.get("minute_plan") or {}
                    confirm_price = minute_plan.get("confirm_price_60m")
                    confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
                    buy_type_map = {"sweet_zone": "甜品区", "breakout": "突破", "panic_buy": "恐慌盘"}
                    buy_type = buy_type_map.get(signal.signal_type, signal.signal_type) if signal else "基础"
                    source_text = source_label_map.get(candidate.get("watch_source", ""), "观察")
                    note = candidate.get("watch_priority_label", "观察")
                    if idx == 1:
                        note = f"{note}，优先看它能否继续证明自己"
                    observation_lines.append(
                        f"| {candidate.get('name')} | {source_text} | {buy_type} | {confirm_text} | 第{idx}顺位 | {note} |"
                    )
                observation_lines.append("")
            top_watch = display_observation_candidates[0]
            top_signal = top_watch.get("signal")
            observation_lines.append(f"**观察优先对象**: {top_watch.get('name')}({top_watch.get('code')})")
            observation_lines.append(
                f"- **原因**: {top_watch.get('watch_priority_label', '观察优先')}；"
                f"{top_watch.get('reason', top_watch.get('tomorrow_risk', '当前优先盯它的承接变化'))}"
            )
            if top_signal:
                entry_range = top_watch.get("entry_range", (top_signal.entry_price, top_signal.entry_price))
                minute_plan = top_watch.get("minute_plan") or {}
                stop_plan = top_watch.get("stop_plan")
                price_focus = build_trade_price_focus(minute_plan, stop_plan)
                confirm_price = minute_plan.get("confirm_price_60m")
                observation_price_focus_text = build_observation_price_focus_text(price_focus)
                observation_lines.append(f"- **跟踪区间**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
                if confirm_price:
                    observation_lines.append(f"- **09:50-10:10观察价**: {confirm_price:.2f}")
                if observation_price_focus_text and observation_price_focus_text != "-":
                    observation_lines.append(f"- **价格怎么盯**: {observation_price_focus_text}")
                if should_surface_price_note(price_focus):
                    observation_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
                observation_lines.append(f"- **参考依据**: {top_watch.get('ev_model_source', '类型先验')}")
                observation_lines.append("- **观察纪律**: 只记录是否继续走强，不构成明日买入指令")
            observation_lines.append("")
        else:
            observation_lines.extend(["**无执行资格候选**: 当前没有进入执行层的标的，只保留观察池", ""])

    conclusion_lines = ["**结论**:"]
    if best_stock:
        signal = best_stock.get("signal")
        if signal:
            entry_range = best_stock.get("entry_range", (signal.entry_price, signal.entry_price))
            buy_type_map = {
                "sweet_zone": "甜品区买入",
                "breakout": "放量突破买入",
                "panic_buy": "恐慌盘买入",
            }
            buy_type = buy_type_map.get(signal.signal_type, signal.signal_type)
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append(f"- **怎么买**: {buy_type}")
            conclusion_lines.append(f"- **到什么价位再动手**: {entry_range[0]:.2f}-{entry_range[1]:.2f}")
            display_position_pct = safe_float(best_stock.get("position_pct", signal.position_pct))
            conclusion_lines.append(f"- **仓位放多少**: {display_position_pct:.0f}%")
            stop_plan = best_stock.get("stop_plan") or build_stop_execution_plan(
                signal.entry_price,
                best_stock.get("stop_loss", signal.stop_loss),
                structure_label="日线预估结构止损",
            )
            minute_plan = best_stock.get("minute_plan") or {}
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            if confirm_price:
                conclusion_lines.append(f"- **09:50-10:10观察价**: {confirm_price:.2f}")
            conclusion_lines.append(f"- **价格怎么盯**: {price_focus.get('compact_text', '-')}")
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {price_focus.get('note_text', '-')}")
            conclusion_lines.append(f"- **参考依据**: {best_stock.get('ev_model_source', '类型先验')}")
            conclusion_lines.append("- **出手时怎么做**: 明日按竞价表态、开盘前几分钟承接、打板/回封、09:50-10:10窗口分层参与，买后用失效价和单笔-5%底线处理风险；其他标的无论多诱人都**禁止操作**")
        else:
            conclusion_lines.append(f"- **如果要买只买谁**: {best_stock.get('name')}({best_stock.get('code')})")
            conclusion_lines.append("- **出手时怎么做**: 明日按固定交易窗口条件触发，买后用失效价和单笔-5%底线处理风险，其他标的禁止操作")
    else:
        if ten_confirm_upgrade_candidate:
            conclusion_lines.append(
                f"- **盘前不抢跑**: {ten_confirm_upgrade_candidate.get('name')}({ten_confirm_upgrade_candidate.get('code')})只保留盘中确认路径，不按盘前0%直接否定"
            )
            conclusion_lines.append("- **确认后怎么做**: 09:50-10:10站上确认价，且板块承接不塌，才评估50%条件执行；未命中继续0%不参与")
        elif trade_gate_open and watch_anchor:
            conclusion_lines.append(f"- **明天先盯哪只**: {watch_anchor.get('name')}({watch_anchor.get('code')})")
            conclusion_lines.append("- **现在是什么情况**: 市场允许出手，但还没有缩到一只可买股，明日先等它自己证明")
        else:
            conclusion_lines.append("- **明天没有可买对象**: 明日不产生买入动作")
        conclusion_lines.append(f"- **明天能不能开仓**: {front_structure_layer_text}")
        if observation_anchor:
            minute_plan = observation_anchor.get("minute_plan") or {}
            stop_plan = observation_anchor.get("stop_plan")
            price_focus = build_trade_price_focus(minute_plan, stop_plan)
            confirm_price = minute_plan.get("confirm_price_60m")
            confirm_text = f"{confirm_price:.2f}" if confirm_price else "待盘中确认"
            observation_price_focus_text = build_observation_price_focus_text(price_focus)
            anchor_type = observation_anchor.get("watch_anchor_type") or watch_anchor_type or "观察对象"
            conclusion_lines.append(f"- **{anchor_type}**: {observation_anchor.get('name')}({observation_anchor.get('code')})")
            conclusion_lines.append(
                f"- **{'现在重点盯什么' if trade_gate_open else '现在重点看什么'}**: "
                f"{compose_observation_focus_text(confirm_text, observation_price_focus_text)}"
            )
            append_watch_anchor_note(conclusion_lines, observation_anchor)
            if should_surface_price_note(price_focus):
                conclusion_lines.append(f"- **价格怎么看**: {build_observation_price_note_text(price_focus)}")
            if trade_gate_open:
                conclusion_lines.append("- **出手时怎么做**: 只能等它走成明天唯一能买的那只后再买，盘中强也不允许提前抢跑")
            elif ten_confirm_upgrade_candidate:
                conclusion_lines.append("- **出手时怎么做**: 盘前0%只代表不抢跑；09:50-10:10窗口内条件成立后，再评估50%条件执行")
            elif final_gate.get("allow_attack_50_ready"):
                conclusion_lines.append("- **当前先不抢**: 0%不参与，只做固定交易窗口条件确认；强核心看竞价表态、开盘前几分钟或回封，普通结构只看09:50-10:10窗口")
            else:
                conclusion_lines.append(f"- **当前只观察**: {position_level}，不新增参与")
        else:
            conclusion_lines.append("- **明天先怎么观察**: 空仓观望")
    conclusion_lines.append("")

    return {
        "lines": [],
        "exports": {
            "pending_lines": sanitize_user_visible_text(pending_lines),
            "observation_lines": sanitize_user_visible_text(observation_lines),
            "conclusion_lines": sanitize_user_visible_text(conclusion_lines),
        },
        "module_logs": [],
    }
