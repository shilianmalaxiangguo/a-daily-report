# Stage 2 Explorer Notes

只读探索完成，没有改文件。

## Existing data capability

* Market stage: `scripts/report/market_structure_judgement.py` can already output index feel, turnover structure, rotation quality, mainline quality, tomorrow rhythm, and candidate contraction principle. Gap: not yet normalized to `启动 / 发酵 / 高潮 / 退潮 / 冰点`.
* Fund structure: market-level funds are spread across market base, Top50/Top20, financing, and turnover; sector-level funds are concentrated in mainline turnover summary, mainline attack evidence, and hot-sector turnover watch rows.
* Sector relationships: mainline capacity summary already has main attack line, rival/background line, relationship state, process, and tomorrow action.
* `超车 / 失速 / 窗口`: existing `build_overtake_window_summary` and rendered rows already express rival slowdown, own-line acceptance, speed gap, failure condition, and tomorrow verification.
* Leader/core validation: existing dragon pullback review and sector internal analysis can provide core anchor, elastic vehicle, rear acceptance, second-wave new high, and sector fund flow.

## Minimal stage 2 recommendation

First render only main conclusions:

1. market stage;
2. fund structure summary;
3. sector relationship table;
4. `超车 / 失速 / 窗口`;
5. leader/core validation summary.

These should appear before candidate stocks.

Keep as appendix first:

* long cycle calendar;
* full mainline turnover history;
* LHB details;
* market capacity evolution long explanation;
* full sector internal analysis table;
* technical diagnostics and data acquisition checklist.

Do not rewrite collectors. Assemble stage 2 context from existing `market_research_snapshot`, mainline turnover summary, market structure judgment, and sector internal analysis.

## Recommended tests and replay checks

* Extend `tests/test_front_page_v2_renderer.py` to assert market stage, fund structure, sector relationships, `超车 / 失速 / 窗口`, and leader/core validation appear before candidate sections.
* Extend `tests/test_market_research_renderer.py` to cover confirmed attack, chaotic rotation, and no attack relationship/window wording.
* Add cycle label mapping tests around market structure judgment if a mapper is introduced.
* Replay command: `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay`.
* Replay check: candidate stocks should not appear before market/fund/sector spine; object identity must not be rewritten downstream.

## Conflict risks

* `市场基底` and `市场结构判断` both explain market background; merge into market stage.
* `周期与主线` capacity, attack evidence, and turnover-share trend should become main conclusion plus appendix evidence.
* `资金意图` must be validation, not independent direction decision.
* `市场容量演化` overlaps with mainline capacity and should move appendix.
* `龙头回头复核` and `板块内部分析` both validate core/elastic; main body needs only a concise summary.
* `最终结论 / 明日执行计划 / 个股裁决` can still repeat object identity and must read the shared final object later.
