from __future__ import annotations

__all__ = [
    "build_helper_diagnostics",
    "clear_helper_logs",
    "drain_helper_logs",
    "record_helper_log",
    "render_helper_diagnostics_lines",
]

_helper_logs = []


def record_helper_log(module, step, status, message, **details):
    _helper_logs.append(
        {
            "module": module,
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def drain_helper_logs():
    logs = list(_helper_logs)
    _helper_logs.clear()
    return logs


def clear_helper_logs():
    _helper_logs.clear()


def _normalize_target_keys(details):
    target_keys = details.get("target_keys") or []
    if isinstance(target_keys, str):
        return [target_keys]
    return [str(item) for item in (target_keys or []) if str(item).strip()]


def build_helper_diagnostics(module_logs=None):
    module_logs = list(module_logs or [])
    error_logs = [log for log in module_logs if str(log.get("status", "") or "") == "error"]
    degraded_logs = [log for log in module_logs if str(log.get("status", "") or "") == "degraded"]
    return {
        "summary": {
            "helper_log_count": len(module_logs),
            "error_count": len(error_logs),
            "degraded_count": len(degraded_logs),
        },
        "issues": [
            {
                "module": str(log.get("module", "") or ""),
                "step": str(log.get("step", "") or ""),
                "status": str(log.get("status", "") or ""),
                "message": str(log.get("message", "") or ""),
                "provider": str((log.get("details") or {}).get("provider", "") or ""),
                "target_keys": _normalize_target_keys(log.get("details") or {}),
                "error": str((log.get("details") or {}).get("error", "") or ""),
                "details": log.get("details") or {},
            }
            for log in module_logs
        ],
    }


def render_helper_diagnostics_lines(diagnostics):
    diagnostics = diagnostics or {}
    summary = diagnostics.get("summary") or {}
    issues = diagnostics.get("issues") or []
    lines = [
        "",
        "=" * 60,
        "🧰 辅助接口体检摘要",
        "=" * 60,
        "辅助日志: {helper_log_count} | 错误: {error_count} | 降级: {degraded_count}".format(
            helper_log_count=summary.get("helper_log_count", 0),
            error_count=summary.get("error_count", 0),
            degraded_count=summary.get("degraded_count", 0),
        ),
    ]
    if issues:
        for item in issues[:8]:
            lines.append(
                "  - {step} | provider={provider} | target={target} | status={status} | error={error}".format(
                    step=item.get("step", "-"),
                    provider=item.get("provider", "-") or "-",
                    target=", ".join(item.get("target_keys", []) or []) or "-",
                    status=item.get("status", "-"),
                    error=item.get("error", "") or item.get("message", "-"),
                )
            )
    else:
        lines.append("✅ 辅助接口未发现异常。")
    return lines
