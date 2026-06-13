# Fix Event Title Evidence Classification

## Goal

Fix the serious classification bug where event titles such as conferences, expos, launches, and forums are classified as policy catalyst without evidence. Classification must be based on verifiable title evidence or fetched/news-derived source facts; when evidence is insufficient, the system must keep the event neutral/unknown instead of guessing.

## In Scope

- Locate the event/news catalyst classification path that produced `政策催化`.
- Add a regression test for conference/expo/forum/product-launch titles that must not become policy catalyst from title shape alone.
- Change the smallest necessary classification logic so unknown or commercial event titles do not use policy catalyst as a fallback.
- Use existing report-date `xuangubao_data.xuangubao_news` rows as news candidates before classification, and attach source evidence only after a structured AI decision confirms the candidate belongs to the same event.
- Preserve existing confirmed policy-catalyst behavior when the title contains direct policy/regulator/official-document evidence.

## Out of Scope

- Rewriting the full event taxonomy.
- Adding a new live web-search provider or changing model providers.
- Using current-web results or undated news rows to classify historical replay events.
- Re-generating historical daily reports unless the fixed code path is proven to be part of report generation for a target date.
- Touching unrelated current worktree changes.

## Non-goals

- Do not use model choice as the correctness boundary.
- Do not guess from low-evidence titles.
- Do not turn missing evidence into a tradeable conclusion.

## Done Definition

- A focused unit test fails before the code change and passes after it.
- Accepted report-date news evidence includes provider, query date, source date, source URL status, evidence text, match confidence, and policy-evidence status in output.
- The fix keeps direct policy titles classified as policy catalyst.
- Relevant narrow tests pass under `.generated/venv-py314/bin/python3.14 -m unittest ...`.
- Commit-prep audit is run with subagents if the platform exposes a subagent tool; if not, the missing tool is reported and a local audit is performed.

## Verification

- Run the new/updated unit test.
- Run the narrow existing test module around event/news classification if found.
- Inspect git diff to ensure only in-scope files changed.

## Technical Notes

- User supplied examples dated 2026-06-05 through 2026-06-25: Huawei Cloud conference, Zhongguancun digital finance conference, global data week, OpenVAN product launch, gas industry exhibition, open-source summit.
- Correct product rule: title/news retrieval only proposes candidates; structured evidence judgment comes before classification. No-evidence fallback must be neutral/unknown, not policy catalyst.
