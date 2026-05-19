import time

from knowledge.trading_philosophy import (
    DECISION_GATE_CHAIN,
    PARTICIPATION_WINDOW_LAYER_TEXT,
    use_contract_logic_digest_text,
    use_execution_framework_text,
)
from report.surface_wording import sanitize_user_visible_text


HOOK_NAME = "infer.strategy_contract"


def run(ctx):
    started_at = time.perf_counter()
    derived = ctx.get("derived") or {}
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    phase = str(market_phase.get("phase", "") or "observe").strip()
    primary_line = str(mainline.get("primary_line", "") or "未知").strip()
    warnings = []
    if "market_phase" not in derived:
        warnings.append("missing derived.market_phase")
    if "mainline" not in derived:
        warnings.append("missing derived.mainline")

    if phase == "defend":
        contract_label = "defense_observe"
        permission_label = "watch_only"
        action_plan = "环境未开，只观察主线与旧仓处理，不做新增参与"
    elif primary_line in ("", "未知"):
        contract_label = "probe_only"
        permission_label = "watch_only"
        action_plan = "主线未清，只保留观察资格，先看探针和竞争线，不授予执行资格"
    else:
        contract_label = "standard_attack"
        permission_label = "execute_50"
        action_plan = f"沿{primary_line}预演50%标准进攻，前提是次日按参与窗口分层确认：{PARTICIPATION_WINDOW_LAYER_TEXT}；不满足即0%不参与"

    gate_chain = list(DECISION_GATE_CHAIN)
    gate_chain_text = " -> ".join(gate_chain)
    contract_reason = f"phase={phase}; primary_line={primary_line}; gate={gate_chain_text}"
    strategy_contract = sanitize_user_visible_text({
        "contract_label": contract_label,
        "permission_label": permission_label,
        "contract_reason": contract_reason,
        "action_plan": action_plan,
        "gate_chain": gate_chain,
        "gate_chain_text": gate_chain_text,
        "execution_framework_text": use_execution_framework_text(),
        "contract_logic_digest_text": use_contract_logic_digest_text(),
    })
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline"],
        "assumptions": ["trading philosophy is converted into a reusable strategy contract"],
        "formula": "map market phase and mainline clarity into a strategy contract",
        "output_keys": ["derived.strategy_contract"],
        "confidence": 0.75 if not warnings else 0.55,
        "warnings": warnings,
    }

    return {
        "value": {"strategy_contract": contract_label},
        "patches": {
            "derived": {"strategy_contract": strategy_contract},
            "diagnostics": {"derivations": {"strategy_contract": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "degraded" if warnings else "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": warnings,
        },
        "artifacts": {},
    }
