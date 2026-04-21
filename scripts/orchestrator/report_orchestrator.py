from hooks.infer.use_execution_permission import run as run_execution_permission
from hooks.infer.use_mainline_analysis import run as run_mainline_analysis
from hooks.infer.use_market_phase import run as run_market_phase
from hooks.input.use_hot_rank import run as run_hot_rank
from hooks.persist.use_snapshot_persistence import run as run_snapshot_persistence
from hooks.report.use_markdown_document import run as run_markdown_document

from orchestrator.pipeline_runner import run_pipeline


def _build_minimal_sections(ctx):
    request = ctx.get("request") or {}
    target_date = request.get("target_date", "")
    derived = ctx.get("derived") or {}
    decision = ctx.get("decision") or {}
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    execution_permission = decision.get("execution_permission") or derived.get("execution_permission") or {}

    preamble = f"# {target_date} A股日报".strip()
    summary_lines = ["## Summary"]
    phase = str(market_phase.get("phase", "") or "").strip() or "unknown"
    primary_line = str(mainline.get("primary_line", "") or "").strip() or "未知"
    permission = str(execution_permission.get("label", "") or "").strip() or "unknown"
    summary_lines.append(f"- market_phase: {phase}")
    summary_lines.append(f"- mainline: {primary_line}")
    summary_lines.append(f"- execution_permission: {permission}")

    return {
        "value": {"sections": {"preamble": preamble, "summary": "\n".join(summary_lines)}},
        "patches": {
            "sections": {
                "preamble": preamble,
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
        ("infer.execution_permission", run_execution_permission),
        ("report.sections", _build_minimal_sections),
        ("report.markdown_document", run_markdown_document),
        ("persist.snapshot", run_snapshot_persistence),
    ]
    return run_pipeline(request=request, hooks=hooks)
