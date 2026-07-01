# Design: 修复 2026-06-29 日报提交前阻断项

## Scope And Boundaries

This task fixes the current official 2026-06-29 report delivery surface. It does not redesign the whole daily-report system.

In scope:

- field normalization for sector fund-flow rows;
- visible Ta/Tb/Tc timeline parity between Markdown and Bear HTML;
- old-position wording consistency for 太极实业 and 深科技;
- acceptance-audit coverage for the visible failure modes;
- regeneration of the 2026-06-29 official report artifacts.

Out of scope:

- adding new providers;
- changing database schema;
- broad replay/backtest rewrites;
- cleaning unrelated dirty files.

## Contracts / Data Flow

### Sector Fund Flow

Source rows may contain different aliases:

- name: `name`, `sector`, `industry`
- net flow: `zljlr`, `net_amount`, `net_inflow`, `net_inflow_yi`
- change: `zdf`, `change_pct`, `pct_change`
- turnover: `turnover_yi`, `amount`, `cje`

Normalized rows used by renderers must include:

```python
{
    "name": "...",
    "zljlr": float,  # unit: yi
    "zdf": float,    # pct
    ...
}
```

Rendering should still tolerate aliases, but normalization is the preferred fix.

### Ta/Tb/Tc Timeline

One timeline truth should drive both surfaces:

- Markdown: a simple table readable in Bear/Obsidian/plain text.
- Bear HTML: existing styled `position-timeline` block.

For 2026-06-29:

- previous source day: 2026-06-28, old path/old holding: 太极实业(600667);
- report day: 2026-06-29;
- execution day: 2026-06-30;
- Ta path: Ta+1 on report day, Ta+2 on execution day;
- Tb path: report day confirms 深科技(000021), execution day is Tb+0 conditional buy, next day is Tb+1 plan handling;
- Tc path: no early occupation, must state no Tc+0.

### Old Position Wording

If the timeline has an old path target, front-page account wording must not claim the holding is unknown. It should state that 太极实业 is the old path to confirm/handle before or alongside the 深科技 execution check.

### Daily Judgment Panel

The existing decision-loop contract allows unresolved rows, but formal report quality requires unresolved rows to be visually separated and not presented as settled conclusions. Acceptance audit should flag excessive unresolved facts in official output when the report claims completion.

## Compatibility / Migration

- Keep report file names and entry commands unchanged.
- Preserve existing HTML timeline structure and CSS classes.
- Keep old sector-flow aliases readable for callers that still send legacy shapes.
- Avoid deleting old tests that protect unknown-holding behavior; add narrower tests for the new known-old-path case.

## Tradeoffs

- Normalizing at request and tolerating aliases at render time is slightly redundant, but safer for old snapshots and replay payloads.
- Markdown table duplicates part of the HTML timeline, but this is intentional because the user reads Markdown and Bear HTML as separate artifacts.
- Acceptance audit should catch clear visible defects without rejecting every legitimate unresolved replay field.

## Rollback / Roll-forward

Rollback:

- revert the small code/test changes and regenerate the report from the previous code if needed.

Roll-forward:

- if another date exposes the same issue, run the same generation and acceptance commands after this fix.
