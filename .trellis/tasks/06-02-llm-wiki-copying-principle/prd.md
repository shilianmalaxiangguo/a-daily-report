# record copying principle in llm wiki

## Goal

Record the user's durable learning principle in the LLM Wiki: copying is not the problem; the risk is copying without knowing the focus, mechanism, and underlying idea.

## In Scope

- Add the principle to `wiki/交易思想/AI摩擦与知识复利.md`.
- Expose a compact field mapping in `scripts/knowledge/llm_wiki_context.py`.
- Add focused tests that prove the wiki text and compact context contain the principle.

## Out of Scope

- Do not change daily report generation behavior beyond the existing LLM Wiki compact context.
- Do not add new wiki pages, routers, or knowledge subsystems.
- Do not change trading decision rules.

## Non-goals

- Do not turn this into generic product strategy documentation.
- Do not treat copying as blind duplication; the recorded principle must emphasize focus, idea, feedback, and migration.

## Done Definition

- `AI摩擦与知识复利` records the copying-learning principle.
- `build_llm_wiki_context()` exposes a compact field mapping for the same principle.
- Focused tests pass with Python 3.14.

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context.LlmWikiContextTest.test_ai_friction_wiki_records_copying_with_focus_and_idea`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context`

## Technical Notes

- Existing wiki routing already sends AI use, knowledge nodes, and knowledge compounding questions to `wiki/交易思想/AI摩擦与知识复利.md`.
- Existing dirty changes in `scripts/knowledge/llm_wiki_context.py` and `tests/test_llm_wiki_context.py` predate this task and must be preserved.
