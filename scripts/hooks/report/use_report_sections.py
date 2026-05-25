import time

from knowledge.trading_philosophy import build_trading_philosophy_snapshot
from report.stage_renderer import render_stage_board
from report.surface_wording import sanitize_user_visible_text


HOOK_NAME = "report.sections"


def _normalize_permission_label(label):
    label = str(label or "").strip()
    if label == "attack_50_ready":
        return "execute_50"
    return label or "unknown"


def _build_environment_section(phase, primary_line, knowledge):
    return "\n".join(
        [
            "## 环境",
            f"- 市场阶段：{phase}",
            f"- 主线：{primary_line}",
            f"- 主推导链：{knowledge.get('main_derivation_chain_text', '')}",
        ]
    )


def _build_observation_section(primary_line, strategy_contract, knowledge, report_stages):
    digest = str(
        strategy_contract.get("contract_logic_digest_text", "")
        or knowledge.get("contract_logic_digest_text", "")
        or ""
    ).strip()
    stage_board = render_stage_board(report_stages)
    return "\n".join(
        [
            "## 观察",
            f"- 当前聚焦：{primary_line}",
            f"- 交易链核心：{digest}",
            "",
            stage_board,
        ]
    )


def _build_execution_section(contract_label, permission, action_plan, knowledge):
    return sanitize_user_visible_text("\n".join(
        [
            "## 执行",
            f"- 合同层：{contract_label}",
            f"- 执行资格：{permission}",
            f"- 动作摘要：{action_plan.get('headline', '')}",
            f"- 触发条件：{action_plan.get('trigger', '')}",
            f"- 动作原因：{action_plan.get('rationale', '')}",
            f"- 执行条件链：{knowledge.get('decision_gate_chain_text', '')}",
            f"- 执行框架：{knowledge.get('execution_framework_text', '')}",
        ]
    ))


def _has_ai_friction_update(request):
    updates = request.get("knowledge_updates") or []
    for update in updates:
        if not isinstance(update, dict):
            continue
        topic = str(update.get("topic", "") or "")
        source_path = str(update.get("source_path", "") or "")
        if "AI摩擦与知识复利" in topic or "AI摩擦与知识复利" in source_path:
            return True
    return False


def build_ai_friction_knowledge_note(request):
    if not _has_ai_friction_update(request or {}):
        return []
    return [
        "## 知识复利提示",
        "- 复利方向：用反馈机制校准新知识，避免只堆积结论。",
        "- 必要认知摩擦：复述、重写、对比或沉淀成知识节点。",
        "- 日报落点：只记录字段化结论，不把文章长文带入交易主链。",
    ]


def _format_knowledge_compounding_candidate(candidate):
    if not isinstance(candidate, dict):
        return ""
    related_nodes = [
        str(node or "").strip()
        for node in candidate.get("related_nodes") or []
        if str(node or "").strip()
    ]
    node_text = " + ".join(related_nodes)
    status = str(candidate.get("status") or "待确认").strip() or "待确认"
    insight = str(candidate.get("new_insight") or "").strip()
    action = str(candidate.get("action") or "").strip()
    parts = [f"{node_text}：{status}" if node_text else status]
    if insight:
        parts.append(insight)
    if action:
        parts.append(action)
    return "- " + "；".join(parts)


def build_knowledge_compounding_candidate_note(llm_wiki):
    candidates = (llm_wiki or {}).get("knowledge_compounding_candidates") or []
    lines = [
        _format_knowledge_compounding_candidate(candidate)
        for candidate in candidates
    ]
    lines = [line for line in lines if line]
    if not lines:
        return []
    return ["## 知识复利候选", *lines]


def _build_review_section(knowledge, llm_wiki=None, request=None):
    wiki = llm_wiki or {}
    request = request or {}
    lines = [
        "## 知识模块",
        f"- 交易思想版本：{knowledge.get('version', 'unknown')}",
        f"- 来源：{knowledge.get('source', 'unknown')}",
        f"- 源文件：{knowledge.get('source_path', '')}",
        f"- LLM Wiki版本：{wiki.get('version', 'unknown')}",
        f"- Wiki来源：{wiki.get('source', 'unknown')}",
    ]
    note_lines = build_ai_friction_knowledge_note(request)
    if note_lines:
        lines.extend(["", note_lines[0].replace("## ", "### ", 1), *note_lines[1:]])
    candidate_lines = build_knowledge_compounding_candidate_note(wiki)
    if candidate_lines:
        lines.extend(["", candidate_lines[0].replace("## ", "### ", 1), *candidate_lines[1:]])
    process_flows = wiki.get("process_flows") or []
    if process_flows:
        lines.extend(["", "```text", str(process_flows[0]).strip(), "```"])
    return "\n".join(lines)


def _build_summary_section(phase, primary_line, contract_label, permission, knowledge):
    return _build_summary_section_with_stages(phase, primary_line, contract_label, permission, knowledge, [])


def _build_summary_section_with_stages(phase, primary_line, contract_label, permission, knowledge, report_stages):
    stage_keys = [str(item.get("stage_key", "") or "").strip() for item in (report_stages or []) if str(item.get("stage_key", "") or "").strip()]
    return "\n".join(
        [
            "## Summary",
            f"- market_phase: {phase}",
            f"- mainline: {primary_line}",
            f"- strategy_contract: {contract_label}",
            f"- execution_permission: {permission}",
            f"- philosophy_version: {knowledge.get('version', 'unknown')}",
            f"- stage_keys: {', '.join(stage_keys) if stage_keys else '-'}",
        ]
    )


def run(ctx):
    started_at = time.perf_counter()
    request = ctx.get("request") or {}
    target_date = request.get("target_date", "")
    derived = ctx.get("derived") or {}
    decision = ctx.get("decision") or {}
    knowledge_root = ctx.get("knowledge") or {}
    knowledge = (knowledge_root.get("trading_philosophy") or {})
    llm_wiki = knowledge_root.get("llm_wiki") or {}
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    strategy_contract = derived.get("strategy_contract") or {}
    report_stages = derived.get("report_stages") or []
    action_plan = decision.get("action_plan") or {}
    execution_permission = decision.get("execution_permission") or derived.get("execution_permission") or {}

    if not knowledge:
        knowledge = build_trading_philosophy_snapshot(
            target_date=target_date,
            run_mode=request.get("run_mode", "frozen"),
            has_personal_positions=bool(request.get("has_personal_positions", False)),
        )

    phase = str(market_phase.get("phase", "") or "unknown").strip() or "unknown"
    primary_line = str(mainline.get("primary_line", "") or "未知").strip() or "未知"
    contract_label = str(strategy_contract.get("contract_label", "") or "unknown").strip() or "unknown"
    permission = _normalize_permission_label(execution_permission.get("label", ""))
    preamble = "\n".join(knowledge.get("report_preamble_lines") or [f"# {target_date} A股日报"]).strip()

    sections = sanitize_user_visible_text({
        "preamble": preamble,
        "environment": _build_environment_section(phase, primary_line, knowledge),
        "observation": _build_observation_section(primary_line, strategy_contract, knowledge, report_stages),
        "execution": _build_execution_section(contract_label, permission, action_plan, knowledge),
        "review": _build_review_section(knowledge, llm_wiki, request),
        "summary": _build_summary_section_with_stages(phase, primary_line, contract_label, permission, knowledge, report_stages),
    })

    return {
        "value": {"sections": sections},
        "patches": {"sections": sections},
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": [],
        },
        "artifacts": {},
    }
