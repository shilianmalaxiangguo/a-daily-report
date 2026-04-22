def make_module_log(hook_name, diagnostics=None, patches=None, artifacts=None, status=None, error=None):
    diagnostics = diagnostics or {}
    patches = patches or {}
    artifacts = artifacts or {}
    resolved_status = status or diagnostics.get("status") or ("error" if error else "success")
    return {
        "hook_name": hook_name,
        "status": resolved_status,
        "duration_ms": diagnostics.get("duration_ms", 0),
        "warnings": list(diagnostics.get("warnings", []) or []),
        "output_zones": list((patches or {}).keys()),
        "artifacts": list((artifacts or {}).keys()),
        "fallback_used": bool(diagnostics.get("fallback_used", False)),
        "error": str(error) if error else "",
    }
