import time

from knowledge.trading_philosophy import PARTICIPATION_WINDOW_LAYER_TEXT
from report.surface_wording import sanitize_user_visible_text


HOOK_NAME = "decision.action_plan"


def run(ctx):
    started_at = time.perf_counter()
    derived = ctx.get("derived") or {}
    decision = ctx.get("decision") or {}
    market_phase = derived.get("market_phase") or {}
    mainline = derived.get("mainline") or {}
    strategy_contract = derived.get("strategy_contract") or {}
    execution_permission = decision.get("execution_permission") or derived.get("execution_permission") or {}

    phase = str(market_phase.get("phase", "") or "observe").strip()
    primary_line = str(mainline.get("primary_line", "") or "未知").strip()
    contract_label = str(strategy_contract.get("contract_label", "") or "unknown").strip()
    permission_label = str(execution_permission.get("label", "") or strategy_contract.get("permission_label", "") or "unknown").strip()
    contract_rationale = str(strategy_contract.get("action_plan", "") or strategy_contract.get("contract_reason", "") or "").strip()

    if permission_label == "attack_50_ready":
        action_label = "execute_50"
        headline = f"沿{primary_line}进入50%标准进攻"
        trigger = f"次日按参与窗口分层确认：{PARTICIPATION_WINDOW_LAYER_TEXT}"
        rationale = contract_rationale or f"{primary_line}仍在趋势比价链内，满足后按50%标准进攻；不满足转为0%不参与"
        permission_label = "execute_50"
    elif contract_label == "defense_observe" or phase == "defend":
        action_label = "watch_only"
        headline = "只观察，不开新仓"
        trigger = "等待环境条件重新满足"
        rationale = contract_rationale or "环境未开，只处理观察和旧仓"
    else:
        action_label = "watch_only"
        headline = "先观察，不授予执行资格"
        trigger = "等待主线更清晰并完成60分钟确认"
        rationale = contract_rationale or "当前只保留观察权"

    payload = sanitize_user_visible_text({
        "action_label": action_label,
        "headline": headline,
        "trigger": trigger,
        "rationale": rationale,
        "contract_label": contract_label,
        "permission_label": permission_label,
    })
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["derived.market_phase", "derived.mainline", "derived.strategy_contract", "decision.execution_permission"],
        "assumptions": ["action summary should be derived from contract first, permission second"],
        "formula": "map strategy contract and permission into a single next-action summary",
        "output_keys": ["decision.action_plan"],
        "confidence": 0.7,
        "warnings": [],
    }

    return {
        "value": {"action_plan": action_label},
        "patches": {
            "decision": {"action_plan": payload},
            "diagnostics": {"derivations": {"action_plan": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": [],
        },
        "artifacts": {},
    }
