from copy import deepcopy

ALLOWED_ZONES = {
    "request",
    "raw",
    "normalized",
    "derived",
    "decision",
    "knowledge",
    "sections",
    "rendered",
    "diagnostics",
    "runtime",
}


def _deep_merge_dicts(base, overlay):
    merged = deepcopy(base or {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged.get(key), value)
        else:
            merged[key] = deepcopy(value)
    return merged


def build_empty_context(request):
    return {
        "request": dict(request),
        "raw": {},
        "normalized": {},
        "derived": {},
        "decision": {},
        "knowledge": {},
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
        if isinstance(payload, dict):
            merged[zone] = _deep_merge_dicts(merged.get(zone), payload)
        else:
            merged[zone] = deepcopy(payload)
    return merged
