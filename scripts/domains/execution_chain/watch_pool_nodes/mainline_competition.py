from report.mainline_turnover_summary_support import (
    normalize_display_text_by_tag_pool,
    resolve_mainline_attack_evidence_summary,
)


def _has_confirmed_attack(context):
    summary = resolve_mainline_attack_evidence_summary(context)
    if not summary:
        return True
    return bool(summary.get("primary_line")) and summary.get("attack_state") == "confirmed_attack"


def _confirmed_attack_line(context):
    summary = resolve_mainline_attack_evidence_summary(context)
    if summary.get("attack_state") == "confirmed_attack":
        return normalize_display_text_by_tag_pool(summary.get("primary_line"), context).strip()
    return ""


def _downgrade_row(item, reason="资金未明显胜出，不能确认为主攻线"):
    downgraded = dict(item or {})
    if str(downgraded.get("role") or "").strip() == "主攻线":
        downgraded["role"] = "候选观察"
    if str(downgraded.get("judgement") or "").strip() in ("", "当前最值得粘住的方向", "最强"):
        downgraded["judgement"] = reason
    if str(downgraded.get("action") or "").strip() in ("", "只在这条线里找买入资格", "只盯核心"):
        downgraded["action"] = "只观察强弱，不给买入资格"
    return downgraded


def build_watch_pool_mainline_competition_node(context, node_meta=None, node_lookup=None):
    snapshot = context.get("mainline_competition_snapshot", []) or []
    if not snapshot:
        return {"lines": [], "exports": {}, "module_logs": []}

    confirmed_line = _confirmed_attack_line(context)
    if not _has_confirmed_attack(context):
        snapshot = [_downgrade_row(item) for item in snapshot]
    elif confirmed_line:
        aligned = []
        for item in snapshot:
            sector = normalize_display_text_by_tag_pool((item or {}).get("sector"), context).strip()
            if sector and sector != confirmed_line and str((item or {}).get("role") or "").strip() == "主攻线":
                aligned.append(_downgrade_row(item, reason="已不是当前确认方向，不能确认为主攻线"))
            else:
                aligned.append(item)
        snapshot = aligned

    lines = [
        "**主线竞争格局**（不是板块名单，而是能量争夺排序）",
        "| 角色 | 方向 | 当前证据 | 判断 | 操作原则 |",
        "|------|------|----------|------|----------|",
    ]
    for item in snapshot:
        sector = normalize_display_text_by_tag_pool(item.get("sector", "-"), context)
        lines.append(
            f"| {item.get('role', '-')} | {sector} | {item.get('evidence', '-')} | "
            f"{item.get('judgement', '-')} | {item.get('action', '-')} |"
        )
    lines.append("")
    return {"lines": lines, "exports": {}, "module_logs": []}
