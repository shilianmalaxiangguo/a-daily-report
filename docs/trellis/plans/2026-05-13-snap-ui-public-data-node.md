# Snap UI Public Data Node Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily-report publish node that prepares and verifies all `snap-ui` public data before any online release is considered complete.

**Architecture:** Implement a small Python service under `scripts/publish/` and a hook wrapper under `scripts/hooks/publish/`. The service orchestrates the existing Tushare turnover pipeline, `snap-ui` static export, local contract checks, and writes a manifest plus checkbox task list.

**Tech Stack:** Python 3.11, unittest, existing Tushare pipeline/storage/export modules, existing `snap-ui` npm contract tests.

---

## File Structure

- Create: `scripts/publish/__init__.py`  
  Package marker for publish services.
- Create: `scripts/publish/snap_ui_public_data.py`  
  Service that runs tasks, records status, writes manifest and checklist.
- Create: `scripts/hooks/publish/__init__.py`  
  Package marker for publish hooks.
- Create: `scripts/hooks/publish/use_snap_ui_public_data.py`  
  Hook-compatible wrapper for `report_orchestrator`.
- Modify: `scripts/orchestrator/report_orchestrator.py`  
  Add `publish.snap_ui_public_data` after `persist.snapshot`.
- Modify: `scripts/daily_report_entry_demo.py`  
  Replace best-effort static sync with publish-node execution after snapshot save.
- Create: `tests/test_snap_ui_public_data_publish_node.py`  
  Unit tests for success and failure behavior.
- Modify: `tests/test_snap_ui_static_sync.py`  
  Update legacy expectations so static sync is no longer best-effort for release data.

## Task 1: Publish Service Contract

**Files:**
- Create: `tests/test_snap_ui_public_data_publish_node.py`
- Create: `scripts/publish/__init__.py`
- Create: `scripts/publish/snap_ui_public_data.py`

- [ ] **Step 1: Write failing success-path test**

Create `tests/test_snap_ui_public_data_publish_node.py` with a test that calls `publish_snap_ui_public_data()` using fake dependencies. Assert:

- returned status is `success`
- manifest exists
- task list exists
- task list has checked entries
- Tushare pipeline was called for the target date
- contract command was called

- [ ] **Step 2: Run success-path test and verify RED**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_public_data_publish_node
```

Expected: FAIL because `publish.snap_ui_public_data` does not exist yet.

- [ ] **Step 3: Implement minimal publish service**

Create `scripts/publish/snap_ui_public_data.py` with:

- `SnapUiPublicDataPublishError`
- `PublishTaskRecorder`
- `publish_snap_ui_public_data(target_date, ...)`
- manifest writer
- markdown checklist writer

The first implementation should use injectable callables for:

- turnover pipeline runner
- static export runner
- contract check runner

- [ ] **Step 4: Run success-path test and verify GREEN**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_public_data_publish_node
```

Expected: PASS.

## Task 2: Failure Stops Release Data Completion

**Files:**
- Modify: `tests/test_snap_ui_public_data_publish_node.py`
- Modify: `scripts/publish/snap_ui_public_data.py`

- [ ] **Step 1: Write failing failure-path test**

Add a test where the contract check runner raises `subprocess.CalledProcessError`. Assert:

- `publish_snap_ui_public_data()` raises `SnapUiPublicDataPublishError`
- manifest exists and has `status: failed`
- task list contains a `Failure:` line
- contract task is not checked

- [ ] **Step 2: Run failure-path test and verify RED**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_public_data_publish_node
```

Expected: FAIL until failure manifest behavior is implemented.

- [ ] **Step 3: Implement failure recording**

Update the service to catch step failures, write failed manifest/checklist, and re-raise `SnapUiPublicDataPublishError`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_public_data_publish_node
```

Expected: PASS.

## Task 3: Daily Entry Integration

**Files:**
- Modify: `tests/test_snap_ui_static_sync.py`
- Modify: `scripts/daily_report_entry_demo.py`

- [ ] **Step 1: Update failing legacy integration tests**

Change `tests/test_snap_ui_static_sync.py` so it expects:

- `publish_snap_ui_public_data` is imported or called
- the old best-effort sync helper no longer swallows release-data failures
- daily entry calls the publish node after `_save_data_snapshot(...)`

- [ ] **Step 2: Run integration tests and verify RED**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_static_sync
```

Expected: FAIL because daily entry still uses best-effort static sync.

- [ ] **Step 3: Wire daily entry to publish node**

Update `scripts/daily_report_entry_demo.py` to call:

```python
publish_snap_ui_public_data(target_date, root=Path(__file__).resolve().parents[1])
```

after `_save_data_snapshot(...)`.

- [ ] **Step 4: Run integration tests and verify GREEN**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_snap_ui_static_sync
```

Expected: PASS.

## Task 4: Orchestrator Hook

**Files:**
- Create: `scripts/hooks/publish/__init__.py`
- Create: `scripts/hooks/publish/use_snap_ui_public_data.py`
- Modify: `scripts/orchestrator/report_orchestrator.py`
- Modify: `tests/test_report_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator test**

Add an assertion in `tests/test_report_orchestrator.py` that `build_report()` includes a module log with `hook_name == "publish.snap_ui_public_data"` after `persist.snapshot`.

- [ ] **Step 2: Run orchestrator test and verify RED**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_report_orchestrator
```

Expected: FAIL because the hook is not registered.

- [ ] **Step 3: Implement hook wrapper and register it**

Create `scripts/hooks/publish/use_snap_ui_public_data.py` with a `run(ctx)` function that calls the publish service and returns diagnostics/artifacts. Register it after `persist.snapshot`.

- [ ] **Step 4: Run orchestrator test and verify GREEN**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest tests.test_report_orchestrator
```

Expected: PASS.

## Task 5: Focused Verification And Commit

**Files:**
- All files changed above

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
PYTHONPATH=scripts venv/bin/python3 -m unittest \
  tests.test_snap_ui_public_data_publish_node \
  tests.test_snap_ui_static_sync \
  tests.test_report_orchestrator \
  tests.test_cloudflare_free_turnover_pipeline \
  tests.test_cloudflare_free_json_export \
  tests.test_database_service \
  tests.test_cloudflare_free_daily_db \
  tests.test_d1_sync_service \
  tests.test_r2_artifact_writer \
  tests.test_tushare_turnover_service
```

Expected: all tests pass.

- [ ] **Step 2: Review git diff**

Run:

```bash
git diff --stat
git diff --check
```

Expected: scoped files only, no whitespace errors.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add scripts/publish scripts/hooks/publish scripts/orchestrator/report_orchestrator.py scripts/daily_report_entry_demo.py tests/test_snap_ui_public_data_publish_node.py tests/test_snap_ui_static_sync.py tests/test_report_orchestrator.py
git commit -m "feat: add snap ui public data publish node"
```

- [ ] **Step 4: Push branch**

Run:

```bash
git push origin develop
```

Expected: remote `develop` contains the implementation commit.

## Self-Review

- Spec coverage: the plan covers the service, failure policy, checklist, manifest, daily entry integration, orchestrator hook, and focused verification.
- Placeholder scan: no TBD/TODO placeholders are left in the plan.
- Type consistency: public function names are consistent across tasks: `publish_snap_ui_public_data`, `SnapUiPublicDataPublishError`, and hook name `publish.snap_ui_public_data`.
