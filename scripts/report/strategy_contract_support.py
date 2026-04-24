from __future__ import annotations

import daily_report_markdown_hooks as markdown_hooks

__all__ = [
    "build_alignment_pool_text",
    "build_strategy_positioning_lines",
    "build_trading_philosophy_lines",
    "get_contract_logic_digest_text",
]


def build_trading_philosophy_lines(include_system_requirement=True, compact=False):
    return markdown_hooks.use_trading_philosophy_lines(
        include_system_requirement=include_system_requirement,
        compact=compact,
    )


def build_strategy_positioning_lines(compact=False):
    return markdown_hooks.use_strategy_positioning_lines(compact=compact)


def get_contract_logic_digest_text():
    return markdown_hooks.use_contract_logic_digest_text()


def build_alignment_pool_text(market_research_snapshot=None, watch_anchor=None, special_probe_verdict=None):
    market_research_snapshot = market_research_snapshot or {}
    observation = market_research_snapshot.get("observation", {}) or {}
    state_machine = market_research_snapshot.get("state_machine", {}) or {}
    watch_anchor = watch_anchor or {}
    special_probe_verdict = special_probe_verdict or {}

    monthly_pool = []
    fermentation_pool = []
    seen = set()

    def append_unique(target, value):
        name = str(value or "").strip()
        if not name or name in seen:
            return
        target.append(name)
        seen.add(name)

    for item in observation.get("mainline_competition_snapshot", []) or []:
        role = str(item.get("role", "") or "").strip()
        sector = str(item.get("sector", "") or "").strip()
        if role in ("主攻线", "次强线"):
            append_unique(monthly_pool, sector)
        elif role == "竞争线":
            append_unique(fermentation_pool, sector)

    if not monthly_pool:
        append_unique(monthly_pool, state_machine.get("leading_line", ""))
        for name in observation.get("mainline_candidates", []) or []:
            append_unique(monthly_pool, name)
            if len(monthly_pool) >= 2:
                break

    for name in observation.get("secondary_candidates", []) or []:
        append_unique(fermentation_pool, name)
        if len(fermentation_pool) >= 3:
            break

    for item in observation.get("sector_trend_snapshot", []) or []:
        append_unique(fermentation_pool, item.get("sector", ""))
        if len(fermentation_pool) >= 3:
            break

    probe_candidate = special_probe_verdict.get("probe_candidate", {}) or {}
    probe_sector = str(
        watch_anchor.get("sector")
        or watch_anchor.get("sector_name")
        or probe_candidate.get("sector")
        or probe_candidate.get("sector_name")
        or ""
    ).strip()
    if not probe_sector and fermentation_pool:
        probe_sector = fermentation_pool[0]

    parts = []
    if monthly_pool:
        parts.append(f"月度站队池：{' / '.join(monthly_pool[:2])}")
    if fermentation_pool:
        parts.append(f"本周发酵方向：{' / '.join(fermentation_pool[:3])}")
    if probe_sector:
        parts.append(f"探针方向：{probe_sector}")
    return "；".join(parts)
