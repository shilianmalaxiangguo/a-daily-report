from hooks.decision.use_action_plan import run as run_action_plan
from hooks.infer.use_execution_permission import run as run_execution_permission
from hooks.infer.use_mainline_analysis import run as run_mainline_analysis
from hooks.infer.use_market_phase import run as run_market_phase
from hooks.infer.use_strategy_contract import run as run_strategy_contract
from hooks.input.use_hot_rank import run as run_hot_rank
from hooks.knowledge.use_trading_philosophy import run as run_trading_philosophy
from hooks.persist.use_snapshot_persistence import run as run_snapshot_persistence
from hooks.report.use_markdown_document import run as run_markdown_document
from hooks.report.use_report_sections import run as run_report_sections
from orchestrator.pipeline_runner import run_pipeline


def build_report(request):
    hooks = [
        ("input.hot_rank", run_hot_rank),
        ("infer.market_phase", run_market_phase),
        ("infer.mainline", run_mainline_analysis),
        ("infer.strategy_contract", run_strategy_contract),
        ("infer.execution_permission", run_execution_permission),
        ("knowledge.trading_philosophy", run_trading_philosophy),
        ("decision.action_plan", run_action_plan),
        ("report.sections", run_report_sections),
        ("report.markdown_document", run_markdown_document),
        ("persist.snapshot", run_snapshot_persistence),
    ]
    return run_pipeline(request=request, hooks=hooks)
