# 狙击手视角买卖策略与T002纪律实施计划

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让正式 spec 可被人快速找到，并保持 wiki / 日报前台 / replay 的口径与 spec 一致。

**Architecture:** 不新增新的交易层或数据层，只在现有 wiki 文档和日报前台口径上做最小对齐。运行时逻辑已在当前工作树完成主体重构，这次只补 discoverability、术语一致性和回归校验。

**Tech Stack:** Python 3.14、现有日报渲染器、现有 wiki Markdown、`unittest`、日报 replay 脚本。

---

## Task 1: Make the spec discoverable from wiki entry points

**Files:**
- Modify: `wiki/README.md`
- Modify: `wiki/交易思想/做T与风险控制.md`

- [ ] **Step 1: Add a short pointer to the formal spec**

Update the wiki entry path so a reader who lands on `做T与风险控制.md` can immediately找到正式 spec，且不需要翻代码。建议只加一行短说明，不改已有交易口径。

Example addition:

```md
正式 spec：`docs/trellis/specs/2026-05-31-sniper-trading-strategy-design.md`
```

- [ ] **Step 2: Keep the pointer visible from the wiki index**

In `wiki/README.md`, keep `做T与风险控制.md` in the usage order and add the same spec pointer near the existing step 8 entry so the doc is easy to discover from the index.

- [ ] **Step 3: Verify the doc links are present**

Run:

```bash
rg -n "2026-05-31-sniper-trading-strategy-design|做T与风险控制" wiki/README.md wiki/交易思想/做T与风险控制.md
```

Expected: both files show the spec pointer, and no trading wording changes are introduced beyond the pointer.

## Task 2: Re-verify report output against the strategy spec

**Files:**
- Verify: `tests/test_front_page_v2_renderer.py`
- Verify: `tests/test_report_runtime.py`
- Verify: `tests/test_report_acceptance_audit.py`
- Verify: `scripts/daily_report_entry_demo.py`
- Verify: `reports/replay/2026-05-29_A股日报_完整版_replay.md`

- [ ] **Step 1: Run the focused test suite**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer tests.test_report_runtime tests.test_report_acceptance_audit
```

Expected: PASS.

- [ ] **Step 2: Re-run the replay sample**

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-05-29 --replay --position '我的仓位是5手京能电力，2手华电辽能'
```

Expected: replay succeeds, `0%原因` remains explicit, and `买点失败仓` is still preserved in the front page output.

- [ ] **Step 3: Confirm the replay wording**

Run:

```bash
rg -n "0%原因|买点失败仓|市场情绪冰点|市场情绪退潮未止跌" reports/replay/2026-05-29_A股日报_完整版_replay.md
```

Expected: the replay contains an explicit non-participation reason and the failure仓 wording is not softened away.
