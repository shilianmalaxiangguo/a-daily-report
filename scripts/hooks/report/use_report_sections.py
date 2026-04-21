import time

from knowledge.trading_philosophy import build_trading_philosophy_snapshot


HOOK_NAME = "report.sections"


def _build_environment_section(phase, primary_line, knowledge):
    return "\n".join(
        [
            "## 环境",
            f"- 市场阶段：{phase}",
            f"- 主线：{primary_line}",
            f"- 主推导链：{knowledge.get('main_derivation_chain_text', '')}",
        ]
    )


def _build_observation_section(primary_line, strategy_contract, knowledge):
    digest = str(
        strategy_contract.get("contract_logic_digest_text", "")
        or knowledge.get("contract_logic_digest_text", "")
        or ""
    ).strip()
    return "\n".join(
        [
            "## 观察",
            f"- 当前聚焦：{primary_line}",
            f"- 交易链核心：{digest}",
        ]
    )


def _build_execution_section(contract_label, permission, action_plan, knowledge):
    return "\n".join(
        [
            "## 执行",
            f"- 合同层：{contract_label}",
            f"- 执行权限：{permission}",
            f"- 动作摘要：{action_plan.get('headline', '')}",
            f"- 触发条件：{action_plan.get('trigger', '')}",
            f"- 动作原因：{action_plan.get('rationale', '')}",
            f"- 执行门链：{knowledge.get('decision_gate_chain_text', '')}",
            f"- 执行框架：{knowledge.get('execution_framework_text', '')}",
        ]
    )


def _build_review_section(knowledge):
    return "\n".join(
        [
            "## 知识模块",
            f"- 交易思想版本：{knowledge.get('version', 'unknown')}",
            f"- 来源：{knowledge.get('source', 'unknown')}",
            f"- 源文件：{knowledge.get('source_path', '')}",
        ]
    )


def _build_summary_section(phase, primary_line, contract_label, permission, knowledge):
    return "\n".join(
        [
            "## Summary",
            f"- market_phase: {phase}",
            f"- mainline: {primary_line}",
            f"- strategy_contract: {contract_label}",
            f"- execution_permission: {permission}",
            f"- philosophy_version: {knowledge.get('version', 'unknown')}",
        ]
    )


def run(ctx):
    started_at = time.perf_counter()
    request = ctx.get("request") or {}
    target_date = request.get("target_date", "")
    derived = ctx.get("derived") or {}
    decision = ctx.get("decision") or {}
    knowledge = ((ctx.get("knowledge") or {}).get("trading_philosophy") or {})
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    strategy_contract = derived.get("strategy_contract") or {}
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
    permission = str(execution_permission.get("label", "") or "unknown").strip() or "unknown"
    preamble = "\n".join(knowledge.get("report_preamble_lines") or [f"# {target_date} A股日报"]).strip()

    sections = {
        "preamble": preamble,
        "environment": _build_environment_section(phase, primary_line, knowledge),
        "observation": _build_observation_section(primary_line, strategy_contract, knowledge),
        "execution": _build_execution_section(contract_label, permission, action_plan, knowledge),
        "review": _build_review_section(knowledge),
        "summary": _build_summary_section(phase, primary_line, contract_label, permission, knowledge),
    }

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
