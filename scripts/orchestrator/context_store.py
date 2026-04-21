from copy import deepcopy

ALLOWED_ZONES = {
    "request",
    "raw",
    "normalized",
    "derived",
    "decision",
    "sections",
    "rendered",
    "diagnostics",
    "runtime",
}


def build_empty_context(request):
    return {
        "request": dict(request),
        "raw": {},
        "normalized": {},
        "derived": {},
        "decision": {},
        "sections": {},
        "rendered": {},
        "diagnostics": {},
        "runtime": {},
    }


def merge_hook_patches(ctx, patches):
    merged = deepcopy(ctx)
    for zone, payload in (patches or {}).items():
        if zone not in ALLOWED_ZONES:
            raise ValueError(f"unknown context zone: {zone}")
        merged[zone].update(payload or {})
    return merged
