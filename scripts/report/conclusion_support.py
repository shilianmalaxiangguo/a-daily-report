from domains.execution_chain.pk_decision_nodes.candidate_surface_filter import (
    blocked_current_observation_keys,
    candidate_blocks_current_observation_target,
    candidate_can_be_current_observation_target,
    candidate_identity_keys,
    candidate_matches_any_key,
)


def get_watch_anchor_note(watch_anchor):
    return str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()


def format_stock_label(stock):
    if not isinstance(stock, dict):
        return str(stock or "").strip()
    name = str(stock.get("name", "") or "").strip()
    code = str(stock.get("code") or stock.get("stock_code") or "").strip()
    if name and code:
        return f"{name}({code})"
    return name or code or "-"


def existing_position_summary_text(context):
    context = context or {}
    summary = context.get("existing_position_summary")
    if not isinstance(summary, dict):
        personal_position_context = context.get("personal_position_context")
        if isinstance(personal_position_context, dict):
            summary = personal_position_context.get("existing_position_summary")
    if not isinstance(summary, dict) or not summary.get("has_position"):
        return ""
    return str(summary.get("summary") or "").strip()


def existing_position_should_lead(context):
    if not existing_position_summary_text(context):
        return False
    if _old_position_priority_active(context):
        return True
    selected = resolve_selected_position_candidate(context)
    return not (selected and selected_target_is_attack_ready(context))


def _final_target_resolution(context):
    context = context or {}
    resolution = context.get("final_target_resolution")
    if isinstance(resolution, dict) and resolution:
        return resolution
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        resolution = snapshot.get("final_target_resolution")
        if isinstance(resolution, dict) and resolution:
            return resolution
    return {}


def _capital_priority(context):
    decision = (_final_target_resolution(context).get("capital_priority_decision") or {})
    if not isinstance(decision, dict):
        return ""
    return str(decision.get("capital_priority") or "").strip()


def _resolution_target(resolution, *keys):
    for key in keys:
        target = resolution.get(key)
        if candidate_can_be_current_observation_target(target):
            return target
    return {}


def _wait_without_watch_target(context):
    resolution = _final_target_resolution(context)
    if not resolution or _capital_priority(context) != "wait":
        return False
    return not _resolution_target(resolution, "watch_target")


def _blocked_surface_keys(context):
    context = context or {}
    candidates = []
    for key in (
        "selected_position_candidate",
        "front_page_selected_position_candidate",
        "current_core_candidate",
        "best_stock",
        "watch_anchor",
    ):
        candidate = context.get(key)
        if isinstance(candidate, dict):
            candidates.append(candidate)
    for key in ("display_observation_candidates", "observation_candidates", "candidate_quality_samples"):
        value = context.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict):
        for key in ("selected_position_candidate", "best_stock", "watch_anchor"):
            candidate = snapshot.get(key)
            if isinstance(candidate, dict):
                candidates.append(candidate)
        for key in ("display_observation_candidates", "observation_candidates", "candidate_quality_samples"):
            value = snapshot.get(key)
            if isinstance(value, list):
                candidates.extend(value)
    return blocked_current_observation_keys(candidates)


def _surface_candidate(context, candidate):
    if not isinstance(candidate, dict) or not candidate_identity_keys(candidate):
        return {}
    if _wait_without_watch_target(context):
        return {}
    blocked_keys = _blocked_surface_keys(context)
    if candidate_blocks_current_observation_target(candidate) or candidate_matches_any_key(candidate, blocked_keys):
        return {}
    return candidate


def resolve_best_stock(context):
    return _surface_candidate(context, (context or {}).get("best_stock") or {})


def resolve_watch_anchor(context):
    return _surface_candidate(context, (context or {}).get("watch_anchor") or {})


def _old_position_priority_active(context):
    return _capital_priority(context) in {"old_position_t", "old_position", "existing_position", "existing_position_t"}


def _tradable_proxy_priority_active(context):
    return _capital_priority(context) == "tradable_proxy"


def _candidate_is_crossline_observation(candidate):
    if not isinstance(candidate, dict):
        return False
    texts = []
    for key in (
        "source_pool",
        "source_pools",
        "watch_anchor_note",
        "summary_text",
        "reason",
        "why_watch",
        "current_interpretation",
        "candidate_origin",
        "observation_layer",
    ):
        value = candidate.get(key)
        if isinstance(value, (list, tuple, set)):
            texts.extend(str(item or "") for item in value)
        else:
            texts.append(str(value or ""))
    joined = "；".join(text for text in texts if text)
    return any(marker in joined for marker in ("跨线对象", "跨线观察", "crossline"))


def _resolved_target_position_pct(target, fallback=0):
    target = target or {}
    for key in ("target_position_pct", "position_pct", "planned_position_pct"):
        value = target.get(key)
        if value in (None, ""):
            continue
        try:
            return int(float(str(value).replace("%", "").strip()))
        except (TypeError, ValueError):
            continue
    return fallback


def resolve_selected_position_candidate(context):
    resolution = _final_target_resolution(context)
    if resolution:
        if _old_position_priority_active(context):
            resolved = _resolution_target(resolution, "watch_target", "new_entry_target", "process_target", "ascii_trace_target")
            if resolved:
                return resolved
        if _tradable_proxy_priority_active(context):
            resolved = _resolution_target(resolution, "display_target", "tradable_proxy_target")
            if resolved:
                return resolved
        resolved = _resolution_target(resolution, "display_target", "new_entry_target", "watch_target", "process_target")
        if resolved:
            return resolved
        if _wait_without_watch_target(context):
            return {}
    selected = context.get("selected_position_candidate") or {}
    selected = _surface_candidate(context, selected)
    if selected:
        return selected
    return {}


def selected_target_is_attack_ready(context):
    if _old_position_priority_active(context) or _capital_priority(context) == "wait":
        return False
    if _tradable_proxy_priority_active(context):
        resolution = _final_target_resolution(context)
        proxy_target = _resolution_target(resolution, "display_target", "tradable_proxy_target")
        return bool(proxy_target) and _resolved_target_position_pct(proxy_target, fallback=50) >= 50
    position_decision = context.get("position_decision") or {}
    try:
        target_pct = int(float(position_decision.get("target_position_pct") or 0))
    except (TypeError, ValueError):
        target_pct = 0
    return target_pct >= 50


def resolve_today_focus_items(context):
    direct_items = context.get("today_validated_items")
    if direct_items is not None:
        return list(direct_items or [])
    tracking_memory_status = context.get("tracking_memory_status", {}) or {}
    return list(tracking_memory_status.get("today_validated_items", []) or [])


def build_market_outlook_text(context):
    prediction_text = str(context.get("step0_prediction_cn", "") or "").strip()
    action_text = str(context.get("step0_action", "") or "").strip()
    final_gate = context.get("final_gate") or {}
    selected = resolve_selected_position_candidate(context)
    if _old_position_priority_active(context):
        final_action = str(final_gate.get("final_action", "") or "").strip()
        parts = [part for part in (prediction_text, final_action) if part]
        if parts:
            return "；".join(parts)
    if selected and selected_target_is_attack_ready(context):
        final_action = str(final_gate.get("final_action", "") or "").strip()
        parts = [part for part in (prediction_text, final_action) if part]
        if parts:
            return "；".join(parts)
    parts = [part for part in (prediction_text, action_text) if part]
    if parts:
        return "；".join(parts)
    fallback_action = str(final_gate.get("final_action", "") or "").strip()
    if fallback_action:
        return fallback_action
    mainline_text = str(context.get("mainline_label") or context.get("mainline_name") or "").strip()
    if mainline_text:
        return f"先看{mainline_text}是否继续强化"
    return "先看环境确认，不抢判断"


def build_focus_recap_text(context):
    selected = resolve_selected_position_candidate(context)
    if selected:
        if _old_position_priority_active(context):
            return f"{format_stock_label(selected)}：观察对象，旧仓先处理"
        if selected_target_is_attack_ready(context):
            return f"{format_stock_label(selected)}：明日目标标的，固定交易窗口内条件成立才执行"
        return f"{format_stock_label(selected)}：观察对象，先观察强弱与承接"

    best_stock = resolve_best_stock(context)
    if best_stock:
        return f"{format_stock_label(best_stock)}：已缩成明天唯一执行候选"

    core_stocks = context.get("core_stocks") or []
    if core_stocks:
        if _candidate_is_crossline_observation(core_stocks[0]):
            return f"{format_stock_label(core_stocks[0])}：跨线观察，只观察承接"
        final_gate = context.get("final_gate") if isinstance(context.get("final_gate"), dict) else {}
        if not (final_gate.get("can_new_entry") or context.get("trade_gate_open")):
            return f"{format_stock_label(core_stocks[0])}：过程候选，优先观察"
        return f"{format_stock_label(core_stocks[0])}：主线核心候选，优先观察"

    watch_anchor = resolve_watch_anchor(context)
    if watch_anchor:
        note_text = get_watch_anchor_note(watch_anchor)
        recap_text = f"{format_stock_label(watch_anchor)}：继续作为观察对象"
        if note_text:
            recap_text = f"{recap_text}；{note_text}"
        return recap_text

    existing_position = existing_position_summary_text(context)
    if existing_position:
        return f"旧仓处理：{existing_position}"

    today_focus_items = resolve_today_focus_items(context)
    if today_focus_items:
        parts = []
        for item in today_focus_items[:3]:
            stock_label = format_stock_label(item)
            state_text = str(
                item.get("follow_state")
                or item.get("summary")
                or item.get("status")
                or ""
            ).strip()
            if not state_text:
                sources = [str(source or "").strip() for source in item.get("sources", []) if str(source or "").strip()]
                state_text = f"来自{'/'.join(sources)}" if sources else "继续观察"
            parts.append(f"{stock_label}：{state_text}")
        return "；".join(parts)

    return "今天没有新增可信关注对象，明天先空仓观察"


def build_candidate_trade_directive(context):
    core_count = int(context.get("core_count", 0) or 0)
    secondary_count = int(context.get("secondary_count", 0) or 0)
    crossline_count = int(context.get("crossline_count", 0) or 0)

    selected = resolve_selected_position_candidate(context)
    best_stock = resolve_best_stock(context)
    watch_anchor = resolve_watch_anchor(context)
    existing_position = existing_position_summary_text(context)
    if selected:
        if _old_position_priority_active(context):
            return f"板块锚反推已收敛到观察对象{format_stock_label(selected)}，但账户先处理旧仓，不新增参与"
        if selected_target_is_attack_ready(context):
            return f"板块锚反推已收敛到明日目标标的{format_stock_label(selected)}，只看固定交易窗口内条件是否成立"
        else:
            return f"板块锚反推已收敛到观察对象{format_stock_label(selected)}，先观察强弱与承接"
    summary = f"{core_count}只主线核心 / {secondary_count}只备选 / {crossline_count}只跨线观察"
    if best_stock:
        directive = f"先只在主线核心里做减法，目标缩到{format_stock_label(best_stock)}"
    elif core_count > 0:
        directive = "先只在主线核心里做减法，不把跨线对象直接当观察位"
    elif watch_anchor:
        directive = f"主线核心还不够，只把{format_stock_label(watch_anchor)}当观察对象"
    elif existing_position and existing_position_should_lead(context):
        directive = f"不新增参与，先处理旧仓：{existing_position}"
    else:
        directive = "当前还没缩出具备参与资格的对象，先继续观察"
    return f"{summary}；{directive}"


def derive_trade_style(context):
    explicit_style = str(context.get("trade_style", "") or "").strip()
    if explicit_style:
        return explicit_style
    position_level = str(context.get("position_level", "") or "").strip()
    final_gate = context.get("final_gate") or {}
    selected = resolve_selected_position_candidate(context)
    if existing_position_should_lead(context):
        return "旧仓处理"
    if selected and selected_target_is_attack_ready(context):
        return "条件进攻"
    if "空仓" in position_level:
        return "空仓"
    best_stock = resolve_best_stock(context)
    watch_anchor = resolve_watch_anchor(context)
    style_switch = context.get("style_switch", {}) or {}
    style_label = str(
        context.get("market_style_label")
        or context.get("style_label")
        or style_switch.get("style_label", "")
        or ""
    ).strip()
    if final_gate and final_gate.get("can_new_entry") is False:
        return "空仓"
    if style_label and any(keyword in style_label for keyword in ("趋势", "波段")) and (best_stock or watch_anchor):
        return "波段"
    if best_stock:
        return "短线"
    if watch_anchor:
        return "观察"
    return "空仓"


def build_risk_trade_note(context):
    if existing_position_should_lead(context):
        return "先处理旧仓风险，不用新故事修复旧仓情绪"
    selected = resolve_selected_position_candidate(context)
    if selected and selected_target_is_attack_ready(context):
        return "固定交易窗口内条件不成立就回到0%，只接受小亏试错，不接受大亏硬扛"
    best_stock = resolve_best_stock(context)
    rr = best_stock.get("r_reward_ratio")
    if rr not in (None, ""):
        return f"只接受预估赚赔比 1:{float(rr):.1f} 的试错，不接受大亏硬扛"
    final_gate = context.get("final_gate") or {}
    position_level = str(context.get("position_level", "") or "").strip()
    if (final_gate and final_gate.get("can_new_entry") is False) or "空仓" in position_level:
        return "先守回撤，空仓也不承担大亏"
    return "只接受小亏试错，不接受大亏硬扛"


def derive_risk_guard_text(context):
    if existing_position_should_lead(context):
        return "已有旧仓先按持仓预案处理，不为不确定性扩大风险"
    selected = resolve_selected_position_candidate(context)
    if selected and selected_target_is_attack_ready(context):
        return "明日目标标的只看固定交易窗口内条件；不满足回到0%，不为抢跑承担大亏"
    best_stock = context.get("best_stock") or {}
    rr = best_stock.get("r_reward_ratio")
    if rr not in (None, ""):
        return f"预估赚赔比 1:{float(rr):.1f}；先小亏小赚，等偶尔大赚；最晚单笔不超过-5%"
    final_gate = context.get("final_gate") or {}
    if final_gate and final_gate.get("can_new_entry") is False:
        return "当前先守住回撤，不为不确定性承担大亏"
    return "先守纪律，再等赔率；没有确认前不为收益承担大亏"
