from report.trading_time_window_contract import normalize_trading_time_text


def build_entry_plan_overview_node(context, node_meta=None, node_lookup=None):
    stage_label = str(context.get("stage_label", "") or "Step 4").strip() or "Step 4"
    stage_title = str(context.get("stage_title", "") or "明日买点预计算").strip() or "明日买点预计算"
    return {
        "lines": [
            f"#### {stage_label} - {stage_title}",
            "> **先看结论**：只给仍有资格的候选预设买点、确认点和止损锚。",
            f"> **怎么执行**：先把价格区间和纪律定好，盘中只按“{normalize_trading_time_text(context['get_execution_framework_text']())}”执行。",
            "",
        ],
        "exports": {},
        "module_logs": [],
    }
