from __future__ import annotations

__all__ = [
    "build_request_diagnostics",
    "render_request_diagnostics_lines",
]

_ISSUE_STATUSES = {"error", "degraded"}


def _normalize_target_keys(details):
    target_keys = details.get("target_keys") or details.get("target_fields") or []
    if isinstance(target_keys, str):
        return [target_keys]
    return [str(item) for item in (target_keys or []) if str(item).strip()]


def _normalize_request_log(log):
    log = log or {}
    details = log.get("details") or {}
    return {
        "module": str(log.get("module", "") or ""),
        "step": str(log.get("step", "") or ""),
        "status": str(log.get("status", "") or ""),
        "message": str(log.get("message", "") or ""),
        "provider": str(details.get("provider") or details.get("source") or log.get("module", "") or ""),
        "target_keys": _normalize_target_keys(details),
        "error": str(details.get("error") or ""),
        "fallback_used": bool(details.get("fallback_used", False)),
        "upstream_error": str(details.get("upstream_error") or ""),
        "details": details,
    }


def build_request_diagnostics(module_logs=None, data_status=None, step_status=None):
    request_logs = [
        _normalize_request_log(log)
        for log in (module_logs or [])
        if str((log or {}).get("step", "") or "").startswith("request.")
    ]
    failures = [log for log in request_logs if log["status"] == "error"]
    degraded = [log for log in request_logs if log["status"] == "degraded"]
    fallbacks = [log for log in request_logs if log["fallback_used"]]

    return {
        "summary": {
            "request_log_count": len(request_logs),
            "error_count": len(failures),
            "degraded_count": len(degraded),
            "fallback_count": len(fallbacks),
            "healthy_count": sum(1 for log in request_logs if log["status"] not in _ISSUE_STATUSES),
            "data_status_total": len(data_status or {}),
            "data_status_failed": sum(1 for value in (data_status or {}).values() if not value),
            "step_status_total": len(step_status or {}),
            "step_status_failed": sum(1 for value in (step_status or {}).values() if not value),
        },
        "failures": failures,
        "degraded": degraded,
        "fallbacks": fallbacks,
        "request_logs": request_logs,
    }


def render_request_diagnostics_lines(diagnostics):
    diagnostics = diagnostics or {}
    summary = diagnostics.get("summary") or {}
    failures = diagnostics.get("failures") or []
    degraded = diagnostics.get("degraded") or []
    fallbacks = diagnostics.get("fallbacks") or []

    lines = [
        "",
        "=" * 60,
        "🩺 请求体检摘要",
        "=" * 60,
        "请求日志: {request_log_count} | 错误: {error_count} | 降级: {degraded_count} | 回退: {fallback_count}".format(
            request_log_count=summary.get("request_log_count", 0),
            error_count=summary.get("error_count", 0),
            degraded_count=summary.get("degraded_count", 0),
            fallback_count=summary.get("fallback_count", 0),
        ),
        "数据状态失败: {data_status_failed}/{data_status_total} | 步骤状态失败: {step_status_failed}/{step_status_total}".format(
            data_status_failed=summary.get("data_status_failed", 0),
            data_status_total=summary.get("data_status_total", 0),
            step_status_failed=summary.get("step_status_failed", 0),
            step_status_total=summary.get("step_status_total", 0),
        ),
    ]

    if failures:
        lines.append("❌ 明确失败:")
        for item in failures[:8]:
            lines.append(
                "  - {step} | provider={provider} | target={target} | error={error}".format(
                    step=item["step"],
                    provider=item["provider"] or "-",
                    target=", ".join(item["target_keys"]) or "-",
                    error=item["error"] or item["message"] or "-",
                )
            )

    if degraded:
        lines.append("⚠️ 降级/空结果:")
        for item in degraded[:8]:
            lines.append(
                "  - {step} | provider={provider} | target={target} | note={message}".format(
                    step=item["step"],
                    provider=item["provider"] or "-",
                    target=", ".join(item["target_keys"]) or "-",
                    message=item["message"] or "-",
                )
            )

    if fallbacks:
        lines.append("↪ 回退链路:")
        for item in fallbacks[:8]:
            lines.append(
                "  - {step} | provider={provider} | target={target} | upstream={upstream}".format(
                    step=item["step"],
                    provider=item["provider"] or "-",
                    target=", ".join(item["target_keys"]) or "-",
                    upstream=item["upstream_error"] or "-",
                )
            )

    if not failures and not degraded and not fallbacks:
        lines.append("✅ 请求层未发现明确失败、降级或回退。")

    return lines
