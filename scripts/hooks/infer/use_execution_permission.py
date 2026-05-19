from knowledge.trading_philosophy import DECISION_GATE_CHAIN, use_execution_framework_text


HOOK_NAME = "infer.execution_permission"


def run(ctx):
    import time

    started_at = time.perf_counter()
    derived = ctx.get("derived") or {}
    market_phase = derived.get("market_phase") or {}
    phase_missing = "market_phase" not in derived
    mainline_missing = "mainline" not in derived
    strategy_contract = derived.get("strategy_contract") or {}
    phase = (market_phase.get("phase") or "observe").strip()
    mainline = ((derived.get("mainline") or {}).get("primary_line") or "未知").strip()
    gate_chain = list(DECISION_GATE_CHAIN)
    gate_chain_text = " -> ".join(gate_chain)
    execution_framework_text = use_execution_framework_text()

    contract_label = str(strategy_contract.get("contract_label", "") or "").strip()
    label = str(strategy_contract.get("permission_label", "") or "").strip()
    if not label:
        label = "watch_only" if phase == "defend" else "execute_50"
    reason = f"phase={phase}; primary_line={mainline}"
    if contract_label:
        reason = f"{reason}; strategy_contract={contract_label}"
    reason = f"{reason}; chain={gate_chain_text}"
    warnings = []
    if phase_missing:
        warnings.append("missing derived.market_phase")
    if mainline_missing:
        warnings.append("missing derived.mainline")
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline", "derived.strategy_contract"],
        "assumptions": [
            "defensive phase blocks new execution",
            "execution follows the canonical trading-philosophy gate chain",
        ],
        "formula": "prefer strategy contract permission_label, otherwise fallback to market-phase rule",
        "output_keys": ["derived.execution_permission", "decision.execution_permission"],
        "confidence": 0.85 if phase == "defend" else (0.55 if warnings else 0.65),
        "warnings": warnings,
    }
    duration_ms = int((time.perf_counter() - started_at) * 1000)

    return {
        "value": {"execution_permission": label},
        "patches": {
            "derived": {
                "execution_permission": {
                    "label": label,
                    "reason": reason,
                    "framework": {
                        "gate_chain": gate_chain,
                        "gate_chain_text": gate_chain_text,
                        "execution_framework_text": execution_framework_text,
                    },
                }
            },
            "decision": {
                "execution_permission": {
                    "label": label,
                    "reason": reason,
                    "framework": {
                        "gate_chain": gate_chain,
                        "gate_chain_text": gate_chain_text,
                        "execution_framework_text": execution_framework_text,
                    },
                }
            },
            "diagnostics": {"derivations": {"execution_permission": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "degraded" if warnings else "success",
            "duration_ms": duration_ms,
            "confidence": derivation["confidence"],
            "warnings": warnings,
        },
        "artifacts": {},
    }
