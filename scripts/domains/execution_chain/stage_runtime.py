def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "domains.execution_chain.stage_runtime",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_execution_stage_lookup(stage_specs):
    lookup = {}
    for index, spec in enumerate(stage_specs or []):
        stage_key = str(spec.get("stage_key", "") or "").strip()
        if not stage_key:
            continue
        title = str(spec.get("title", "") or stage_key).strip() or stage_key
        lookup[stage_key] = {
            "stage_key": stage_key,
            "title": title,
            "stage_no": index,
            "label": f"Step {index}",
        }
    return lookup


def get_execution_stage_label(stage_lookup, stage_key, suffix=None):
    stage_lookup = stage_lookup or {}
    stage_meta = stage_lookup.get(stage_key) or {}
    base_label = str(stage_meta.get("label", "") or stage_key).strip() or stage_key
    if suffix in (None, ""):
        return base_label
    return f"{base_label}.{suffix}"


def run_registered_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
    stage_specs = list(stage_specs or [])
    stage_lookup = stage_lookup or build_execution_stage_lookup(stage_specs)
    current_context = dict(stage_context or {})
    aggregated_lines = []
    aggregated_logs = []
    stage_outputs = {}
    executed_stages = []

    for spec in stage_specs:
        stage_key = str(spec.get("stage_key", "") or "").strip()
        builder = spec.get("builder")
        if not stage_key or builder is None:
            continue

        stage_meta = dict(stage_lookup.get(stage_key) or {})
        if not stage_meta:
            stage_meta = {
                "stage_key": stage_key,
                "title": str(spec.get("title", "") or stage_key).strip() or stage_key,
                "stage_no": len(executed_stages),
                "label": f"Step {len(executed_stages)}",
            }

        try:
            result = builder(current_context, stage_meta, stage_lookup) or {}
        except Exception as error:
            _append_log(
                aggregated_logs,
                f"run.{stage_key}",
                "error",
                "执行 stage 失败",
                stage_key=stage_key,
                error=str(error),
            )
            raise

        lines = list(result.get("lines") or [])
        exports = dict(result.get("exports") or {})
        module_logs = list(result.get("module_logs") or [])

        aggregated_lines.extend(lines)
        aggregated_logs.extend(module_logs)
        stage_outputs[stage_key] = exports
        current_context.update(exports)
        executed_stages.append(stage_meta)
        _append_log(
            aggregated_logs,
            f"run.{stage_key}",
            "success",
            "已执行 stage",
            stage_key=stage_key,
            line_count=len(lines),
            export_keys=sorted(exports.keys()),
        )

    return {
        "lines": aggregated_lines,
        "context": current_context,
        "module_logs": aggregated_logs,
        "stage_outputs": stage_outputs,
        "stage_lookup": stage_lookup,
        "stages": executed_stages,
    }
