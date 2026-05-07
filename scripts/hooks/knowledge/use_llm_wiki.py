import time

from knowledge.llm_wiki_context import build_llm_wiki_context


HOOK_NAME = "knowledge.llm_wiki"


def run(ctx):
    started_at = time.perf_counter()
    snapshot = build_llm_wiki_context()
    derivation = {
        "hook_name": HOOK_NAME,
        "inputs": ["wiki/README.md", "wiki/交易思想/*.md", "wiki/资料库/缠论原文索引.md"],
        "assumptions": ["LLM Wiki is a compact Chinese knowledge context, not report prose"],
        "formula": "materialize compact wiki boundaries and field mappings",
        "output_keys": ["knowledge.llm_wiki"],
        "confidence": 1.0,
        "warnings": [],
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
            "warnings": [],
        },
        "artifacts": {},
    }
