from report.legacy_stage_summary import build_legacy_report_stage_rows
from report.stage_registry import build_report_stages


def _build_report_stages_from_context(context):
    report_stages = context.get("report_stages") or []
    if report_stages:
        return report_stages

    final_gate = context.get("final_gate") or {}
    return build_report_stages(
        {
            "derived": {
                "market_phase": {"phase": str(context.get("step0_prediction", "") or "").lower()},
                "mainline": {"primary_line": context.get("mainline_name", "")},
                "strategy_contract": {"contract_label": final_gate.get("gate_status", "")},
            },
            "decision": {
                "execution_permission": {"label": "conditional_30" if context.get("trade_gate_open") else "watch_only"},
                "action_plan": {"trigger": context.get("front_follow_action_text", "")},
            },
        }
    )


def _get_watch_anchor_note(watch_anchor):
    return str((watch_anchor or {}).get("watch_anchor_note", "") or "").strip()


def _build_mvp_target_row(context):
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = _get_watch_anchor_note(watch_anchor)

    if best_stock:
        entry_range = best_stock.get("entry_range") or ()
        if len(entry_range) >= 2:
            return (
                "| 如果要买只买谁 | "
                f"{best_stock.get('name')}({best_stock.get('code')})，"
                f"60分钟确认且触及{entry_range[0]:.2f}-{entry_range[1]:.2f}才允许买入 |"
            )
        return (
            "| 如果要买只买谁 | "
            f"{best_stock.get('name')}({best_stock.get('code')})，60分钟确认后按条件触发 |"
        )
    if watch_anchor:
        if trade_gate_open:
            return (
                "| 明天先盯哪只 | "
                f"{watch_anchor.get('name')}({watch_anchor.get('code')})，"
                "先看60分钟确认，只有走成明天唯一能买的那只才允许买入"
                f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
            )
        return (
            "| 重点观察谁 | "
            f"{watch_anchor.get('name')}({watch_anchor.get('code')})，"
            "只看强弱，不构成买入指令"
            f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
        )
    return "| 观察名单 | 当前没有可买对象，只保留观察名单 |"


def _build_full_mode_strategy_row(context):
    final_gate = context.get("final_gate") or {}
    step0_prediction = str(context.get("step0_prediction", "") or "").strip()
    best_stock = context.get("best_stock") or {}
    watch_anchor = context.get("watch_anchor") or {}
    trade_gate_open = bool(context.get("trade_gate_open"))
    watch_anchor_note = _get_watch_anchor_note(watch_anchor)

    if not final_gate.get("can_new_entry"):
        if final_gate.get("should_reduce"):
            return "| **明日策略** | **只处理旧仓** | 继续研究市场，但不新增参与；若你有旧仓先去弱留强 |"
        return "| **明日策略** | **不开新仓，只观察** | 当前裁决不允许新增跟随，先看环境和主线是否继续强化 |"

    if step0_prediction == "DIFFICULT":
        return "| **明日策略** | **开盘再评估** | 环境仍需确认，前30分钟只看环境，60分钟后再定 |"

    if best_stock:
        if step0_prediction == "CLEAR":
            return (
                "| **明日策略** | **执行唯一标的** | "
                f"只操作{best_stock.get('name')}，60分钟确认后执行，买后用30分钟结构止损，其他标的禁止 |"
            )
        return (
            "| **明日策略** | **唯一标的条件触发** | "
            f"只操作{best_stock.get('name')}，60分钟确认后再买，其他标的无论多诱人都禁止 |"
        )

    if watch_anchor:
        if trade_gate_open:
            return (
                "| **明日策略** | **先盯重点盯盘股** | "
                f"只盯{watch_anchor.get('name')}，先做60分钟确认，只有走成明天唯一能买的那只才允许买入"
                f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
            )
        return (
            "| **明日策略** | **不开新仓，只观察** | "
            f"{watch_anchor.get('name')}作为重点观察谁，只看强弱，不下买单"
            f"{'；' + watch_anchor_note if watch_anchor_note else ''} |"
        )

    return "| **明日策略** | **空仓观望** | 无符合条件标的 |"


def build_legacy_final_conclusion_lines(context):
    context = context or {}
    display_mvp_mode = bool(context.get("display_mvp_mode"))
    final_gate = context.get("final_gate") or {}
    abnormal_probe_parts = context.get("abnormal_probe_parts") or []
    lines = [
        "#### 最终结论",
        "> **注**：以下结论基于今日收盘数据，预判明日操作。明日前30分钟先确认环境，买点一律等60分钟确认。",
        "",
    ]

    if display_mvp_mode:
        lines.extend(
            [
                "| 维度 | 明日结论 |",
                "|------|----------|",
                f"| 市场环境 | {context.get('step0_prediction_cn', '')}；{context.get('step0_action', '')} |",
                f"| 明日主看方向 | {context.get('mainline_label') or context.get('mainline_name') or '-'} |",
                (
                    f"| 观察池焦点 | {int(context.get('watchlist_count', 0) or 0)}只观察 / "
                    f"{int(context.get('core_count', 0) or 0)}只主线核心 / "
                    f"{int(context.get('crossline_count', 0) or 0)}只跨线观察 / "
                    f"{int(context.get('abnormal_watch_count', 0) or 0)}只异常承接 |"
                ),
                f"| 明天能不能开仓 | {context.get('front_structure_layer_text', '')} |",
            ]
        )
        if abnormal_probe_parts:
            lines.append(f"| 异常探针 | {'；'.join(abnormal_probe_parts)} |")
        lines.append(_build_mvp_target_row(context))
        lines.append(f"| 明日唯一动作 | {context.get('front_follow_action_text', '')} |")
        lines.append("| 出手时怎么做 | 前30分钟只确认环境；买点必须等60分钟；买后用30分钟结构止损，最晚单笔-5% |")
    else:
        lines.extend(
            [
                "| stage_key | 模块 | 明日指引 |",
                "|-----------|------|----------|",
            ]
        )
        report_stages = _build_report_stages_from_context(context)
        stage_rows = build_legacy_report_stage_rows(
            {
                "report_stages": report_stages,
                "watchlist_count": context.get("watchlist_count", 0),
                "core_count": context.get("core_count", 0),
                "secondary_count": context.get("secondary_count", 0),
                "crossline_count": context.get("crossline_count", 0),
                "risk_summary": context.get("front_structure_layer_text", ""),
                "trade_gate_open": context.get("trade_gate_open", False),
                "best_stock": context.get("best_stock"),
                "watch_anchor": context.get("watch_anchor"),
                "watch_anchor_type": context.get("watch_anchor_type", ""),
                "abnormal_probe_parts": abnormal_probe_parts,
            }
        )
        for row in stage_rows:
            lines.append(f"| {row.get('stage_key', '-')} | {row.get('title', '-')} | {row.get('guidance', '-')} |")
        lines.append(_build_full_mode_strategy_row({**context, "final_gate": final_gate}))

    lines.extend(
        [
            "",
            "> **⚠️ 买点时效性**: 以上买点基于今日收盘数据，明日若直接高开离买点>5%，则放弃；即便价格命中，也要等60分钟确认后再买，买后再用30分钟结构止损。",
            "",
        ]
    )
    return lines
