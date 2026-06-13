# Stage 1 Explorer Notes

只读探索完成，没有改文件。

## Existing entry

The closest unified payload entry is `scripts/report/two_layer_decision_payload.py:build_two_layer_decision_payload`.

Current fields:

- `schema_version`
- `target_date`
- `front_decision`
- `b_level_conditions`
- `derivation_steps`

Runtime builds and stores it in `scripts/report/runtime.py` through `_store_runtime_two_layer_decision_payload` under `data`, `execution_stage_context`, and `market_research_snapshot`.

## Missing fields from parent PRD

- `opening_verdict`
- `market_stage`
- `fund_structure`
- `sector_relationships`
- `overtake_slowdown_window`
- `leader_core_validation`
- `position_stance`
- `candidate_pool_verdict`
- `final_object`
- `next_day_action`
- `historical_correction`
- `section_migration_map`

Stage 1 should focus on the minimal action-facing subset:

- `opening_verdict`
- `position_stance`
- `candidate_pool_verdict`
- `final_object`
- `next_day_action`

## Minimal change recommendation

- Extend `build_two_layer_decision_payload`, do not create a competing payload.
- Keep legacy fields available for current renderers.
- Add tests in `tests/test_two_layer_decision_payload.py` first.
- Stage 1 write scope should prefer:
  - `scripts/report/two_layer_decision_payload.py`
  - `tests/test_two_layer_decision_payload.py`

## Risks

Most likely conflict sections in current replay:

- `最终标的解题过程`
- `明日账户建议`
- `五、个股解读`
- `六、明日执行计划`
- `七、最终结论`
- `推导审计层`
- appendix execution/candidate lifecycle tables

These sections should eventually read `final_object`; stage 1 can establish the packet field and tests before broader renderer migration.
