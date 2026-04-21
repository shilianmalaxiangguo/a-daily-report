from hooks.infer.use_execution_permission import run as run_execution_permission
from hooks.infer.use_mainline_analysis import run as run_mainline_analysis
from hooks.infer.use_market_phase import run as run_market_phase
from hooks.infer.use_strategy_contract import run as run_strategy_contract
from hooks.input.use_hot_rank import run as run_hot_rank
from hooks.knowledge.use_trading_philosophy import run as run_trading_philosophy
from hooks.persist.use_snapshot_persistence import run as run_snapshot_persistence
from hooks.report.use_markdown_document import run as run_markdown_document

from knowledge.trading_philosophy import build_trading_philosophy_snapshot
from orchestrator.pipeline_runner import run_pipeline


def _build_minimal_sections(ctx):
    request = ctx.get("request") or {}
    target_date = request.get("target_date", "")
    derived = ctx.get("derived") or {}
    decision = ctx.get("decision") or {}
    knowledge = ((ctx.get("knowledge") or {}).get("trading_philosophy") or {})
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    strategy_contract = derived.get("strategy_contract") or {}
    execution_permission = decision.get("execution_permission") or derived.get("execution_permission") or {}
    if not knowledge:
        knowledge = build_trading_philosophy_snapshot(
            target_date=target_date,
            run_mode=request.get("run_mode", "frozen"),
            has_personal_positions=bool(request.get("has_personal_positions", False)),
        )

    preamble = "\n".join(knowledge.get("report_preamble_lines") or [f"# {target_date} A股日报"]).strip()
    phase = str(market_phase.get("phase", "") or "").strip() or "unknown"
    primary_line = str(mainline.get("primary_line", "") or "").strip() or "未知"
    contract_label = str(strategy_contract.get("contract_label", "") or "").strip() or "unknown"
    permission = str(execution_permission.get("label", "") or "").strip() or "unknown"
    environment_lines = [
        "## 环境",
        f"- 市场阶段：{phase}",
        f"- 主线：{primary_line}",
        f"- 主推导链：{knowledge.get('main_derivation_chain_text', '')}",
    ]
    observation_lines = [
        "## 观察",
        f"- 当前聚焦：{primary_line}",
        f"- 交易链核心：{knowledge.get('contract_logic_digest_text', '')}",
    ]
    execution_lines = [
        "## 执行",
        f"- 合同层：{contract_label}",
        f"- 执行权限：{permission}",
        f"- 执行门链：{knowledge.get('decision_gate_chain_text', '')}",
        f"- 执行框架：{knowledge.get('execution_framework_text', '')}",
    ]
    review_lines = [
        "## 知识模块",
        f"- 交易思想版本：{knowledge.get('version', 'unknown')}",
        f"- 来源：{knowledge.get('source', 'unknown')}",
        f"- 源文件：{knowledge.get('source_path', '')}",
    ]
    summary_lines = ["## Summary"]
    summary_lines.append(f"- market_phase: {phase}")
    summary_lines.append(f"- mainline: {primary_line}")
    summary_lines.append(f"- strategy_contract: {contract_label}")
    summary_lines.append(f"- execution_permission: {permission}")
    summary_lines.append(f"- philosophy_version: {knowledge.get('version', 'unknown')}")

    return {
        "value": {
            "sections": {
                "preamble": preamble,
                "environment": "\n".join(environment_lines),
                "observation": "\n".join(observation_lines),
                "execution": "\n".join(execution_lines),
                "review": "\n".join(review_lines),
                "summary": "\n".join(summary_lines),
            }
        },
        "patches": {
            "sections": {
                "preamble": preamble,
                "environment": "\n".join(environment_lines),
                "observation": "\n".join(observation_lines),
                "execution": "\n".join(execution_lines),
                "review": "\n".join(review_lines),
                "summary": "\n".join(summary_lines),
            }
        },
        "diagnostics": {"hook_name": "report.sections", "status": "success", "warnings": []},
        "artifacts": {},
    }


def build_report(request):
    hooks = [
        ("input.hot_rank", run_hot_rank),
        ("infer.market_phase", run_market_phase),
        ("infer.mainline", run_mainline_analysis),
        ("infer.strategy_contract", run_strategy_contract),
        ("infer.execution_permission", run_execution_permission),
        ("knowledge.trading_philosophy", run_trading_philosophy),
        ("report.sections", _build_minimal_sections),
        ("report.markdown_document", run_markdown_document),
        ("persist.snapshot", run_snapshot_persistence),
    ]
    return run_pipeline(request=request, hooks=hooks)
