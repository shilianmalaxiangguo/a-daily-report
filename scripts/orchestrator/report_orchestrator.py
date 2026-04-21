from orchestrator.hook_registry import register, resolve
from orchestrator.pipeline_runner import run_pipeline
from hooks.input.use_hot_rank import run as run_hot_rank
from hooks.report.use_markdown_document import run as run_markdown_document


def _register_report_hooks():
    register("input.hot_rank", run_hot_rank)
    register("report.markdown_document", run_markdown_document)


def build_report(request):
    _register_report_hooks()
    hooks = [
        ("input.hot_rank", resolve("input.hot_rank")),
        ("report.markdown_document", resolve("report.markdown_document")),
    ]
    return run_pipeline(request=request, hooks=hooks)
