# Implementation: 板块资金扩散选股生成前审计

## Prerequisites

- Use `.generated/venv-py314/bin/python3.14` for all Python commands.
- Keep this slice to Spec/Wiki/runtime-knowledge updates.
- Do not change the final-target selection algorithm in this task.

## Ordered Checklist

- [x] I1: Add backend Spec scenario for sector-capital-flow pre-generation review.
- [x] I2: Add the Mermaid audit template to the Spec.
- [x] I3: Update LLM Wiki / runtime knowledge wording so future runs retrieve the principle.
- [x] I4: Add or update focused LLM Wiki context/router tests.
- [x] I5: Run focused tests and diff checks.
- [x] I6: Commit on the current task branch.

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `git diff --check`

## Risk And Rollback Points

- Risk: Spec text becomes abstract philosophy rather than executable contract.
  - Mitigation: include contracts, validation matrix, good/base/bad cases, and required tests.
- Risk: Future code still treats limit-up as the entry source.
  - Mitigation: explicitly write wrong/correct examples and LLM Wiki mapping.
- Risk: Scope expands into selection-engine rewrites.
  - Mitigation: keep runtime behavior changes out of this task.

## Review Checkpoints

- After Spec edit: confirm Mermaid expresses `板块资金扩散 -> 资金载体 -> 价格行为 -> 唯一动作`.
- After Wiki/runtime knowledge edit: confirm context test sees the principle.
- Before commit: run `git diff --check` and focused unit test.
