import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from knowledge.llm_wiki_context import (
    build_llm_wiki_context,
    llm_wiki_confidence_for_availability,
)
from knowledge.llm_wiki_router import build_llm_wiki_fact_bundle, route_llm_wiki_knowledge_trace


HOOK_NAME = "knowledge.llm_wiki"
_SHANGHAI_TZ = timezone(timedelta(hours=8))
def _routing_data(ctx):
    data = {}
    for zone in ("request", "raw", "normalized", "derived", "decision"):
        payload = ctx.get(zone) if isinstance(ctx, dict) else None
        if isinstance(payload, dict):
            data.update(payload)
    return data


def run(ctx):
    started_at = time.perf_counter()
    request = ctx.get("request") if isinstance(ctx, dict) else {}
    request = request if isinstance(request, dict) else {}
    target_date = str(request.get("target_date") or "").strip()
    query_date = str(request.get("query_date") or "").strip() or datetime.now(_SHANGHAI_TZ).date().isoformat()
    snapshot = build_llm_wiki_context(target_date=target_date, query_date=query_date)
    availability = str(snapshot.get("availability") or "invalid")
    snapshot_warning_items = snapshot.get("warnings")
    warnings_valid = isinstance(snapshot_warning_items, list)
    warnings = (
        [str(item) for item in snapshot_warning_items]
        if warnings_valid
        else ["知识上下文提醒格式无效，停止生成知识引用"]
    )
    if not target_date:
        warnings.append("目标交易日缺失，知识引用日期无法核对")
    warnings = list(dict.fromkeys(warnings))
    manifest = snapshot.get("manifest")
    manifest_shape_valid = isinstance(manifest, Mapping) and warnings_valid
    if not manifest_shape_valid:
        warnings.append("知识清单缺失或格式无效，停止生成知识引用")
        warnings = list(dict.fromkeys(warnings))
    fact_bundle = build_llm_wiki_fact_bundle(_routing_data(ctx))
    trace = route_llm_wiki_knowledge_trace(
        fact_bundle["facts"],
        manifest=manifest if manifest_shape_valid else None,
        target_date=target_date,
        query_date=query_date,
        facts_source=fact_bundle["facts_source"],
        fact_sources=fact_bundle["fact_sources"],
        warnings=[*warnings, *fact_bundle["warnings"]],
    )
    snapshot["knowledge_trace"] = trace
    snapshot["knowledge_hits"] = [dict(item) for item in trace["hits"]]
    snapshot["availability"] = trace["availability"]
    warnings = list(trace["warnings"])
    snapshot["warnings"] = warnings
    availability = str(snapshot.get("availability") or availability)
    confidence = llm_wiki_confidence_for_availability(availability)
    snapshot["confidence"] = confidence
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["request.target_date", "request.query_date", "knowledge_manifest.v1"],
        "assumptions": ["LLM Wiki is a compact Chinese knowledge context, not report prose"],
        "formula": "materialize compact wiki boundaries and field mappings",
        "output_keys": ["knowledge.llm_wiki"],
        "confidence": confidence,
        "availability": availability,
        "warnings": warnings,
    }
    return {
        "value": {"llm_wiki": snapshot},
        "patches": {
            "knowledge": {"llm_wiki": snapshot},
            "diagnostics": {"derivations": {"llm_wiki": derivation}},
        },
        "diagnostics": {
            "hook_name": HOOK_NAME,
            "status": "success",
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
            "warnings": warnings,
        },
        "artifacts": {"llm_wiki": snapshot},
    }
