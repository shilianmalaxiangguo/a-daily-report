from report.report_shell_node_registry import (
    build_prohibition_section_node_specs,
    build_report_shell_node_specs,
)
from report.report_shell_node_runtime import run_report_shell_nodes
from report.report_shell_nodes import (
    _build_prohibition_payload,
    build_allowed_header_node,
    build_allowed_items_node,
    build_prohibition_environment_node,
    build_prohibition_header_node,
    build_prohibition_items_node,
    build_report_shell_capital_intent_placeholder_node,
    build_report_shell_cycle_mainline_header_node,
    build_report_shell_cycle_calendar_placeholder_node,
    build_report_shell_cycle_interpretation_placeholder_node,
    build_report_shell_blank_node,
    build_report_shell_discipline_header_node,
    build_report_shell_discipline_placeholder_node,
    build_report_shell_execution_plan_header_node,
    build_report_shell_final_summary_placeholder_node,
    build_report_shell_market_base_header_node,
    build_report_shell_market_base_placeholder_node,
    build_report_shell_preamble_node,
    build_report_shell_pivot_mainline_placeholder_node,
    build_report_shell_stock_interpretation_placeholder_node,
    build_risk_section_node,
)


def _append_log(logs, step, status, message, **details):
    logs.append(
        {
            "module": "report.report_document_builder",
            "step": step,
            "status": status,
            "message": message,
            "details": details,
        }
    )


def build_report_shell_contract(
    target_date,
    run_mode="frozen",
    has_personal_positions=False,
    compact=False,
    enabled_node_keys=None,
    *,
    use_report_preamble,
):
    logs = []
    node_context = {
        "target_date": target_date,
        "run_mode": run_mode,
        "has_personal_positions": has_personal_positions,
        "compact": compact,
        "use_report_preamble": use_report_preamble,
    }
    builder_map = {
        "preamble": build_report_shell_preamble_node,
        "discipline_header": build_report_shell_discipline_header_node,
        "discipline_placeholder": build_report_shell_discipline_placeholder_node,
        "market_base_header": build_report_shell_market_base_header_node,
        "market_base_placeholder": build_report_shell_market_base_placeholder_node,
        "cycle_mainline_header": build_report_shell_cycle_mainline_header_node,
        "cycle_calendar_placeholder": build_report_shell_cycle_calendar_placeholder_node,
        "cycle_interpretation_placeholder": build_report_shell_cycle_interpretation_placeholder_node,
        "pivot_mainline_placeholder": build_report_shell_pivot_mainline_placeholder_node,
        "capital_intent_placeholder": build_report_shell_capital_intent_placeholder_node,
        "stock_interpretation_placeholder": build_report_shell_stock_interpretation_placeholder_node,
        "execution_plan_header": build_report_shell_execution_plan_header_node,
        "final_summary_placeholder": build_report_shell_final_summary_placeholder_node,
        "footer": build_report_shell_blank_node,
    }
    node_specs = build_report_shell_node_specs(builder_map, enabled_node_keys=enabled_node_keys)
    runtime_result = run_report_shell_nodes(node_specs, node_context)
    report = runtime_result["lines"]
    return {
        "report": report,
        "module_logs": logs + list(runtime_result.get("module_logs") or []) + [
            {
                "module": "report.report_document_builder",
                "step": "build.report_shell",
                "status": "success",
                "message": "已构建日报文档骨架",
                "details": {"line_count": len(report)},
            }
        ],
    }


def build_prohibition_section_contract(
    display_position_level,
    display_operation_state,
    environment_headline="",
    has_personal_positions=False,
    final_gate=None,
    main_sectors=None,
    exit_analysis=None,
    enabled_node_keys=None,
):
    logs = []
    payload = _build_prohibition_payload(
        display_position_level,
        display_operation_state,
        environment_headline=environment_headline,
        has_personal_positions=has_personal_positions,
        final_gate=final_gate,
        main_sectors=main_sectors,
        exit_analysis=exit_analysis,
    )
    node_context = {"prohibition_payload": payload}
    risk_sector_count = len((exit_analysis or {}).get("risk_sectors", []) or [])
    builder_map = {
        "environment": build_prohibition_environment_node,
        "prohibition_header": build_prohibition_header_node,
        "prohibition_items": build_prohibition_items_node,
        "allowed_header": build_allowed_header_node,
        "allowed_items": build_allowed_items_node,
        "risk_section": build_risk_section_node,
    }
    node_specs = build_prohibition_section_node_specs(builder_map, enabled_node_keys=enabled_node_keys)
    runtime_result = run_report_shell_nodes(node_specs, node_context)
    prohibition_content = runtime_result["lines"]
    return {
        "lines": prohibition_content,
        "module_logs": logs + list(runtime_result.get("module_logs") or []) + [
            {
                "module": "report.report_document_builder",
                "step": "build.prohibition_section",
                "status": "success",
                "message": "已生成次日操作纪律块",
                "details": {
                    "position_level": display_position_level,
                    "operation_state": display_operation_state,
                    "risk_sector_count": risk_sector_count,
                },
            }
        ],
    }


def replace_placeholder_lines(report_lines, marker, replacement_lines):
    for idx, line in enumerate(report_lines):
        if line == marker:
            report_lines[idx : idx + 1] = list(replacement_lines or [])
            return True
    return False
