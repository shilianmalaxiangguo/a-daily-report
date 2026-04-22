import time

from report.stage_registry import build_report_stages


HOOK_NAME = "report.stages"


def run(ctx):
    started_at = time.perf_counter()
    stages = build_report_stages(ctx)
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline", "derived.strategy_contract", "decision.execution_permission", "decision.action_plan"],
        "assumptions": ["report stages should be registry-driven rather than hard-coded step numbers"],
        "formula": "iterate stage registry and materialize current stage list",
        "output_keys": ["derived.report_stages"],
        "confidence": 0.8,
        "warnings": [],
    }

    return {
        "value": {"report_stages": stages},
        "patches": {
            "derived": {"report_stages": stages},
            "diagnostics": {"derivations": {"report_stages": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": [],
        },
        "artifacts": {},
    }
