from __future__ import annotations

import importlib.util
from pathlib import Path

LEGACY_MODULE_BASES = [
    Path("/Users/chaixixi/.workbuddy/skills/a-daily-report/scripts"),
    Path("/Users/chaixixi/WorkBuddy/Claw/scripts"),
]


def load_legacy_module(module_name: str):
    for base in LEGACY_MODULE_BASES:
        candidate = base / f"{module_name}.py"
        if not candidate.exists():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"_legacy_{module_name}", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            continue
    return None


def export_or_default(module_name: str, attr_name: str, default):
    module = load_legacy_module(module_name)
    if module is not None and hasattr(module, attr_name):
        return getattr(module, attr_name)
    return default
