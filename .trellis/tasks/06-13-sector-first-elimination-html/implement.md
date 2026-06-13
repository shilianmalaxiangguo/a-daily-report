# Implementation: 板块先行选股淘汰赛HTML与日报同步生成

## Prerequisites

- Use `.generated/venv-py314/bin/python3.14` for all Python commands.
- Preserve `final_target_resolution` as the only current-action source.
- Do not introduce multiple user-facing明日标的.
- Keep existing uncommitted user changes intact.

## Ordered Checklist

- [ ] I1: Complete child task PRDs and context manifests.
- [ ] I2: Implement elimination evidence payload builder using existing report context.
- [ ] I3: Add focused tests for payload layer counts, reasons, and unique final action.
- [ ] I4: Implement static HTML renderer for the payload.
- [ ] I5: Add focused tests or snapshot-style checks for required HTML sections and no multi-target wording.
- [ ] I6: Wire report generation to write the companion HTML for replay/official paths.
- [ ] I7: Extend acceptance audit or add a narrow check for companion existence and final action consistency.
- [ ] I8: Regenerate 2026-06-12 replay and verify the companion HTML contains 和远气体’s identity-pass/risk-fail path.

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest <focused tests>`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-12 --replay`
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-12_A股日报_完整版_replay.md --companion-html <generated-elimination-html>`
- `git diff --check`

## Risk And Rollback Points

- Risk: HTML introduces another source of final target truth.
  - Mitigation: render final target only from the same final action source and audit consistency.
- Risk: missing historical evidence causes invented elimination reasons.
  - Mitigation: use explicit missing-data rows.
- Risk: existing report output changes too broadly.
  - Mitigation: keep companion generation additive and narrow.

## Review Checkpoints

- After I2/I3: verify payload can represent the 2026-06-12 和远气体 path.
- After I4/I5: visually inspect generated HTML.
- After I6/I7: run replay generation and acceptance audit.
