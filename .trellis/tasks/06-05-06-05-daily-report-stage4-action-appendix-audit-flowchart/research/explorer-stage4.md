# Stage 4 Explorer Notes

只读探索完成，没有改文件。

## Entry points

* Front next-day action/final summary: `scripts/report/front_page_v2_renderer.py`, especially `_execution_plan_lines()` and `_final_summary_lines()`.
* Runtime front-page assembly and two-layer execution conclusion insertion: `scripts/report/runtime.py`.
* Action plan nodes: `scripts/report/action_plan_renderer.py` and `scripts/report/action_plan_node_registry.py`; action table already appears before candidate quality.
* Appendix rendering: `scripts/report/appendix_renderer.py`; runtime demotes old body into `## 八、详细附录`.
* Acceptance audit: `scripts/report/report_acceptance_audit.py`, already has process-evidence heading checks and some object consistency checks.
* Flowchart: no generation script found; only static HTML artifacts. Target file is `reports/flowcharts/当前日报选股到最终标的流转图.html`.

## Minimal stage 4 recommendation

* Do not rewrite the main flow.
* Add or reuse a closing next-day action checklist renderer before detailed appendix:
  * position stance;
  * primary object;
  * execution/observation conditions;
  * no-participation conditions;
  * old-position handling;
  * review points.
* Checklist must read the same final object packet, not candidate quality tables, observation pool, or old body.
* Keep appendix, but mark supporting/process headings clearly.
* Strengthen acceptance audit with a horizontal final-identity check across opening conclusion, final target process, final conclusion, closing action checklist, and path graph.
* Update static Mermaid HTML to the confirmed market-to-action pipeline:
  * market stage;
  * fund structure;
  * sector relationships;
  * overtake/slowdown/window;
  * core validation;
  * position stance;
  * candidate verdict;
  * final object;
  * next-day action checklist;
  * appendix evidence.

## Recommended verification

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit tests.test_report_runtime tests.test_front_page_v2_renderer tests.test_two_layer_decision_payload tests.test_action_plan_renderer
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-04_A股日报_完整版_replay.md
```

Flowchart check: open `reports/flowcharts/当前日报选股到最终标的流转图.html` in browser and confirm Mermaid renders a non-empty Chinese pipeline.

## Risks

* `## 六、明日执行计划`, `## 七、最终结论`, `明日执行结论`, and `最终标的解题过程` can each still look like final conclusions.
* Appendix lists can compete with the final answer unless marked as process evidence.
* `two_layer_decision_payload` is execution-object-biased while `sniper_target_derivation` is observation/final-object-biased; they must eventually share final object identity.
* Current flowchart does not include the closing action checklist and appendix migration.
