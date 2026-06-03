# Lightweight Daily Report Split Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-version split outputs for a human-readable lightweight report, evidence appendix, and run log while preserving the existing full report and summary.

**Architecture:** Keep the existing rendering pipeline intact. Add small pure split helpers in `scripts/daily_report_render.py`, then extend `build_report_outputs()` and `save_report_outputs()` so new variants are generated and saved beside existing report files.

**Tech Stack:** Python 3.14, stdlib `unittest`, existing daily report renderer. All commands must use `.generated/venv-py314/bin/python3.14`.

---

## Scope

### In Scope

- Add new variants:
  - `REPORT_VARIANT_LIGHTWEIGHT = "lightweight"`
  - `REPORT_VARIANT_EVIDENCE_APPENDIX = "evidence_appendix"`
  - `REPORT_VARIANT_RUN_LOG = "run_log"`
- Generate those variants from already-rendered full/summary report text and preflight data.
- Save them with Chinese labels:
  - `轻量版`
  - `证据附录`
  - `运行日志`
- Keep existing `完整版` and `执行摘要` unchanged.
- Add tests for extraction, save naming, and replay-style output contents.

### Out of Scope

- Do not rewrite the market, candidate, or trading decision logic.
- Do not delete old output files.
- Do not capture every stdout line in the run log.
- Do not change report acceptance audit rules.

### Done Definition

- `build_report_outputs()` returns five variants.
- `save_report_outputs()` saves all five variants with correct filenames.
- Lightweight report contains `## 狙击手执行图` and the four scenario labels.
- Evidence appendix starts with `## 证据附录`.
- Run log starts with `## 运行日志` and contains preflight lines.
- Existing tests continue to pass.

## File Structure

- Modify `scripts/daily_report_render.py`
  - Add variant constants.
  - Add label helper for variant filenames.
  - Add pure helpers for lightweight/evidence/log variants.
  - Extend `build_report_outputs()`.
  - Extend `save_report_outputs()` filename labels.
- Modify `tests/test_daily_report_render.py`
  - Add direct unit tests for split helpers and save naming.

## Task 1: Add split variants and pure builders

**Files:**
- Modify: `scripts/daily_report_render.py`
- Modify: `tests/test_daily_report_render.py`

- [ ] **Step 1: Write failing tests**

Add tests to `tests/test_daily_report_render.py`:

```python
    def test_build_report_outputs_returns_lightweight_evidence_and_run_log_variants(self):
        data = {"sections": [{"title": "A股市场分析", "content": "正文"}]}
        outputs = build_report_outputs(data, "2026-05-31", emit_preflight=False)

        self.assertIn(REPORT_VARIANT_FULL, outputs)
        self.assertIn(REPORT_VARIANT_SUMMARY, outputs)
        self.assertIn(REPORT_VARIANT_LIGHTWEIGHT, outputs)
        self.assertIn(REPORT_VARIANT_EVIDENCE_APPENDIX, outputs)
        self.assertIn(REPORT_VARIANT_RUN_LOG, outputs)
        self.assertIn("## 狙击手执行图", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("普通候选", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("强核心", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("已有旧仓", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("失败仓/退潮", outputs[REPORT_VARIANT_LIGHTWEIGHT])
        self.assertIn("## 证据附录", outputs[REPORT_VARIANT_EVIDENCE_APPENDIX])
        self.assertIn("## 运行日志", outputs[REPORT_VARIANT_RUN_LOG])
        self.assertIn("日报关键数据 preflight", outputs[REPORT_VARIANT_RUN_LOG])
```

Also update the import at the top of `tests/test_daily_report_render.py` to include:

```python
    REPORT_VARIANT_EVIDENCE_APPENDIX,
    REPORT_VARIANT_LIGHTWEIGHT,
    REPORT_VARIANT_RUN_LOG,
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render.DailyReportRenderTest.test_build_report_outputs_returns_lightweight_evidence_and_run_log_variants
```

Expected: FAIL because the new constants or variants do not exist.

- [ ] **Step 3: Implement constants and builders**

In `scripts/daily_report_render.py`, add constants near existing variant constants:

```python
REPORT_VARIANT_LIGHTWEIGHT = "lightweight"
REPORT_VARIANT_EVIDENCE_APPENDIX = "evidence_appendix"
REPORT_VARIANT_RUN_LOG = "run_log"
```

Add them to `__all__`.

Add these helpers before `build_report_outputs()`:

```python
SNIPER_ASCII_FLOW = """```text
T日收盘候选
    |
    v
先分型
    |
    +-- 普通候选
    |      -> T+1等MA5回踩
    |      -> 09:50-10:10收回MA5/VWAP/0轴
    |      -> 成立50%，不成立不做
    |
    +-- 强核心
    |      -> 优先MA5回踩
    |      -> 健康低开转强可50%
    |      -> 全天强且偏离不大，尾盘最多25%
    |
    +-- 已有旧仓
    |      -> 先处理可卖旧仓
    |      -> 强势周期MA5入/MA7清/MA5T
    |
    +-- 失败仓/退潮
           -> 买点失败仓先处理
           -> 只给一次修复窗口
           -> 不修复就降风险
```"""


def _section_before(text: str, marker: str) -> str:
    text = str(text or "")
    if marker in text:
        return text.split(marker, 1)[0].rstrip()
    return text.strip()


def _section_from(text: str, marker: str) -> str:
    text = str(text or "")
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return ""


def build_lightweight_report_text(full_report: str, summary_report: str = "") -> str:
    base = _section_before(full_report, "## 八、详细附录")
    if not base.strip():
        base = str(summary_report or full_report or "").strip()
    parts = [base.rstrip(), "", "## 狙击手执行图", SNIPER_ASCII_FLOW]
    parts.append("")
    parts.append("## 证据与运行文件")
    parts.append("- 证据附录：同目录下 `A股日报_证据附录` 文件。")
    parts.append("- 运行日志：同目录下 `A股日报_运行日志` 文件。")
    return "\n".join(parts).strip() + "\n"


def build_evidence_appendix_text(full_report: str, target_date: str = "") -> str:
    appendix = _section_from(full_report, "## 八、详细附录")
    if appendix:
        body = appendix
    else:
        body = "完整版未找到详细附录，保留原始报告供复盘检查。\n\n" + str(full_report or "").strip()
    title = f"# {target_date} A股日报证据附录".strip()
    return f"{title}\n\n## 证据附录\n\n{body.strip()}\n"


def build_run_log_text(preflight: dict, target_date: str, saved_paths: dict | None = None) -> str:
    lines = [f"# {target_date} A股日报运行日志", "", "## 运行日志", ""]
    lines.extend(render_report_preflight_lines(preflight or {}))
    lines.extend(["", "## 日报一致性检查", "", "- 待主流程完成后以终端输出为准。", "", "## 生成文件路径"])
    if saved_paths:
        for variant, path in saved_paths.items():
            lines.append(f"- {variant}: {path}")
    else:
        lines.append("- 保存路径将在写入后由主流程打印。")
    return "\n".join(lines).strip() + "\n"
```

- [ ] **Step 4: Extend `build_report_outputs()`**

Change its return dict to include:

```python
    return {
        REPORT_VARIANT_FULL: _inject_report_variant_banner(full_report, REPORT_VARIANT_FULL),
        REPORT_VARIANT_SUMMARY: _inject_report_variant_banner(summary_report, REPORT_VARIANT_SUMMARY),
        REPORT_VARIANT_LIGHTWEIGHT: build_lightweight_report_text(full_report, summary_report),
        REPORT_VARIANT_EVIDENCE_APPENDIX: build_evidence_appendix_text(full_report, target_date),
        REPORT_VARIANT_RUN_LOG: build_run_log_text(preflight, target_date),
    }
```

- [ ] **Step 5: Run test to verify GREEN**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render.DailyReportRenderTest.test_build_report_outputs_returns_lightweight_evidence_and_run_log_variants
```

Expected: PASS.

## Task 2: Save split variants with readable filenames

**Files:**
- Modify: `scripts/daily_report_render.py`
- Modify: `tests/test_daily_report_render.py`

- [ ] **Step 1: Write failing save naming test**

Add this test:

```python
    def test_save_report_outputs_writes_split_variant_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outputs = {
                REPORT_VARIANT_FULL: "# full",
                REPORT_VARIANT_SUMMARY: "# summary",
                REPORT_VARIANT_LIGHTWEIGHT: "# light",
                REPORT_VARIANT_EVIDENCE_APPENDIX: "# evidence",
                REPORT_VARIANT_RUN_LOG: "# log",
            }

            saved = save_report_outputs(outputs, "2026-05-31", mode=LEDGER_MODE_REPLAY, output_dir=str(root))

            self.assertTrue((root / "2026-05-31_A股日报_完整版_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_执行摘要_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_轻量版_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_证据附录_replay.md").exists())
            self.assertTrue((root / "2026-05-31_A股日报_运行日志_replay.md").exists())
            self.assertEqual(saved[REPORT_VARIANT_LIGHTWEIGHT], str(root / "2026-05-31_A股日报_轻量版_replay.md"))
```

Ensure `tempfile`, `Path`, and `LEDGER_MODE_REPLAY` are already imported in the test file; if any is missing, add it.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render.DailyReportRenderTest.test_save_report_outputs_writes_split_variant_labels
```

Expected: FAIL because unknown variants use the wrong label.

- [ ] **Step 3: Add variant label helper**

In `scripts/daily_report_render.py`, add:

```python
def _report_variant_label(variant: str) -> str:
    labels = {
        REPORT_VARIANT_FULL: "完整版",
        REPORT_VARIANT_SUMMARY: "执行摘要",
        REPORT_VARIANT_LIGHTWEIGHT: "轻量版",
        REPORT_VARIANT_EVIDENCE_APPENDIX: "证据附录",
        REPORT_VARIANT_RUN_LOG: "运行日志",
    }
    return labels.get(variant, str(variant or "报告"))
```

Update `_get_report_output_path()` and `save_report_outputs()` to use `_report_variant_label(variant)` instead of the old two-way `"完整版" if ... else "执行摘要"` expression.

- [ ] **Step 4: Run save test to verify GREEN**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render.DailyReportRenderTest.test_save_report_outputs_writes_split_variant_labels
```

Expected: PASS.

## Task 3: Replay verification

**Files:**
- Verify only unless a previous task failed.

- [ ] **Step 1: Run focused renderer tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_render
```

Expected: PASS.

- [ ] **Step 2: Run 2026-05-29 replay**

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-05-29 --replay --position '我的仓位是5手京能电力，2手华电辽能'
```

Expected: replay succeeds and saves the new split files.

- [ ] **Step 3: Inspect generated files**

Run:

```bash
ls reports/replay/2026-05-29_A股日报_*_replay.md
rg -n "## 狙击手执行图|普通候选|强核心|已有旧仓|失败仓/退潮|0%原因" reports/replay/2026-05-29_A股日报_轻量版_replay.md
rg -n "## 证据附录|附录：数据获取与执行步骤清单" reports/replay/2026-05-29_A股日报_证据附录_replay.md
rg -n "## 运行日志|日报关键数据 preflight|生成文件路径" reports/replay/2026-05-29_A股日报_运行日志_replay.md
```

Expected: all checks find matches.
