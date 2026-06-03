# Candidate Selection Trace Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a candidate selection trace layer that explains how T0/T1/T2/T3 report candidates were selected, renders the explanation as Markdown tables, and saves a structured JSON artifact for review.

**Architecture:** Reuse the existing candidate quality contract as the entry point, and add a focused trace contract module that derives key inputs, checks, branch path, visible summary, and eliminated-cause summaries from existing candidate fields. Extend the existing candidate quality renderer to display compact and full trace tables, and add a small artifact writer that stores the same trace payload under `data/candidate-traces/`.

**Tech Stack:** Python 3.14 stdlib, `unittest`, existing `selection.candidate_quality_contracts`, existing `report.candidate_quality_renderer`, existing action-plan node runtime.

---

## Scope

### In Scope

- T0/T1/T2/T3 candidates get a `trace` object.
- Markdown output includes a compact trace table for T0/T1 and a full trace table for T0/T1/T2/T3.
- Eliminated candidates are summarized by reason, count, and up to three representative names.
- JSON artifact is written to `data/candidate-traces/YYYY-MM-DD.json`.
- Tests cover contract fields, renderer output, artifact writer, and action-plan integration.

### Out of Scope

- No rewrite of candidate generation.
- No new scoring system.
- No full-market tracing.
- No per-stock full trace for eliminated candidates.
- No change to existing T0/T1/T2/T3 meaning.

### Non-goals

- Do not make the report longer by default with every upstream rejected stock.
- Do not create a parallel selection engine.
- Do not store raw行情 arrays, K-line arrays, or full snapshots in the trace artifact.

### Done Definition

- Each displayed T0/T1/T2/T3 candidate has `source_pools`, `key_inputs`, `checks`, `branch_path`, `final_action`, `trigger_condition`, `failure_condition`, `missing_data`, and `visible_summary`.
- Missing key data is visible as `关键数据不完整` or `数据缺失`; it is not converted into a positive reason.
- Renderer output contains `候选选股轨迹` tables and preserves existing candidate quality tables.
- Artifact writer creates valid JSON with `artifact_version`, `trade_date`, `generated_at`, `source_report`, `visible_scope`, `traces`, and `eliminated_summary`.
- All commands use `.generated/venv-py314/bin/python3.14`.

## File Structure

- Create: `scripts/selection/candidate_trace_contracts.py`
  - Owns trace derivation, controlled values, eliminated summary, and artifact payload building.
  - Does not select, score, or reorder candidates.
- Modify: `scripts/selection/candidate_quality_contracts.py`
  - Calls the trace contract builder and stores `trace` on candidate quality contracts.
- Modify: `scripts/report/candidate_quality_renderer.py`
  - Renders compact and full trace tables from existing contracts.
- Modify: `scripts/report/action_plan_nodes.py`
  - Passes trace options and exports `candidate_traces` for downstream artifact writing.
- Create: `scripts/report/candidate_trace_artifacts.py`
  - Writes `data/candidate-traces/YYYY-MM-DD.json` and returns paths/counts.
- Test: `tests/test_candidate_trace_contracts.py`
  - Unit tests for trace contract and eliminated summary.
- Modify: `tests/test_candidate_quality_contracts.py`
  - Regression that existing candidate quality contracts include trace without breaking visible rows.
- Modify: `tests/test_candidate_quality_renderer.py`
  - Renderer table tests.
- Modify: `tests/test_action_plan_renderer.py`
  - Node integration/export test.
- Create: `tests/test_candidate_trace_artifacts.py`
  - Artifact writer test.

## Task 1: Trace Contract Module

**Files:**
- Create: `scripts/selection/candidate_trace_contracts.py`
- Test: `tests/test_candidate_trace_contracts.py`

- [ ] **Step 1: Write the failing trace contract tests**

Create `tests/test_candidate_trace_contracts.py`:

```python
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from selection.candidate_trace_contracts import (
    CHECK_RESULTS,
    build_candidate_trace,
    build_candidate_trace_artifact_payload,
    build_eliminated_summary,
)


class CandidateTraceContractsTest(unittest.TestCase):
    def test_build_candidate_trace_for_t0_condition_observation(self):
        trace = build_candidate_trace(
            {
                "name": "华天科技",
                "code": "002185",
                "tier": "T0",
                "source_pools": ["主线核心候选"],
                "mainline": "半导体",
                "sector": "半导体",
                "market_fit": "部分满足",
                "market_evidence": "市场不支持强进攻，但允许核心候选条件观察",
                "mainline_fit": "满足",
                "mainline_evidence": "半导体仍在主线候选内",
                "stock_structure_fit": "部分满足",
                "stock_structure_evidence": "承接未破，但早盘仍需确认",
                "latest_price": 13.2,
                "available_cash": 10000,
                "trigger_condition": "主线承接 + 个股突破或回踩确认",
                "failure_condition": "主线回落或放量不承接",
                "final_action": "09:50-10:10确认，不满足继续不参与",
            }
        )

        self.assertEqual(trace["stock_code"], "002185")
        self.assertEqual(trace["stock_name"], "华天科技")
        self.assertEqual(trace["tier"], "T0")
        self.assertEqual(trace["source_pools"], ["主线核心候选"])
        self.assertEqual(trace["mainline"], "半导体")
        self.assertEqual(trace["sector"], "半导体")
        self.assertIn({"field": "账户适配", "value": "实际可买", "source": "account_context"}, trace["key_inputs"])
        self.assertEqual([check["result"] for check in trace["checks"]], ["部分满足", "满足", "部分满足"])
        self.assertIn("市场条件部分满足", trace["branch_path"])
        self.assertIn("进入 T0 条件观察", trace["branch_path"])
        self.assertEqual(trace["final_action"], "09:50-10:10确认，不满足继续不参与")
        self.assertEqual(trace["trigger_condition"], "主线承接 + 个股突破或回踩确认")
        self.assertEqual(trace["failure_condition"], "主线回落或放量不承接")
        self.assertEqual(trace["missing_data"], [])
        self.assertLessEqual(len(trace["visible_summary"]), 40)

    def test_missing_data_is_not_positive_reason(self):
        trace = build_candidate_trace(
            {
                "name": "缺数样本",
                "code": "000001",
                "tier": "T1",
                "source_pools": ["主线核心候选"],
                "mainline": "",
                "sector": "",
                "market_fit": "",
                "mainline_fit": "",
                "stock_structure_fit": "",
                "final_action": "",
            }
        )

        results = {check["label"]: check["result"] for check in trace["checks"]}
        self.assertEqual(results["市场条件"], "数据缺失")
        self.assertEqual(results["主线条件"], "数据缺失")
        self.assertEqual(results["个股结构"], "数据缺失")
        self.assertIn("关键数据不完整", trace["final_action"])
        self.assertIn("mainline", trace["missing_data"])
        self.assertIn("sector", trace["missing_data"])
        self.assertIn("市场条件数据缺失", trace["branch_path"])

    def test_check_results_are_controlled(self):
        self.assertEqual(CHECK_RESULTS, ("满足", "部分满足", "未满足", "数据缺失"))
        trace = build_candidate_trace(
            {
                "name": "异常样本",
                "code": "000002",
                "tier": "T2",
                "market_fit": "很强",
                "mainline_fit": "满足",
                "stock_structure_fit": "未满足",
            }
        )
        self.assertEqual(trace["checks"][0]["result"], "数据缺失")
        self.assertEqual(trace["checks"][1]["result"], "满足")
        self.assertEqual(trace["checks"][2]["result"], "未满足")

    def test_build_eliminated_summary_groups_reasons_and_caps_representatives(self):
        summary = build_eliminated_summary(
            [
                {"name": "大众公用", "reason": "主线不匹配"},
                {"name": "红星发展", "reason": "主线不匹配"},
                {"name": "步步高", "reason": "主线不匹配"},
                {"name": "中船特气", "reason": "账户不适配"},
                {"name": "第四只", "reason": "主线不匹配"},
                {"name": "", "reason": ""},
            ]
        )

        by_reason = {item["reason"]: item for item in summary}
        self.assertEqual(by_reason["主线不匹配"]["count"], 4)
        self.assertEqual(by_reason["主线不匹配"]["representatives"], ["大众公用", "红星发展", "步步高"])
        self.assertEqual(by_reason["账户不适配"]["count"], 1)
        self.assertEqual(by_reason["数据缺失"]["treatment"], "关键数据不完整，停止生成动作")

    def test_build_candidate_trace_artifact_payload(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})
        payload = build_candidate_trace_artifact_payload(
            trade_date="2026-05-26",
            traces=[trace],
            eliminated_summary=[{"reason": "主线不匹配", "count": 1, "representatives": ["大众公用"], "treatment": "保留观察，不进入动作分层"}],
            generated_at="2026-05-27T00:00:00+08:00",
            source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
        )

        self.assertEqual(payload["artifact_version"], 1)
        self.assertEqual(payload["trade_date"], "2026-05-26")
        self.assertEqual(payload["visible_scope"], "T0_T1_T2_T3")
        self.assertEqual(payload["traces"][0]["stock_code"], "002185")
        self.assertEqual(payload["eliminated_summary"][0]["reason"], "主线不匹配")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_contracts
```

Expected:

```text
ModuleNotFoundError: No module named 'selection.candidate_trace_contracts'
```

- [ ] **Step 3: Implement the trace contract module**

Create `scripts/selection/candidate_trace_contracts.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone, timedelta


ARTIFACT_VERSION = 1
VISIBLE_SCOPE = "T0_T1_T2_T3"
CHECK_RESULTS = ("满足", "部分满足", "未满足", "数据缺失")
VALID_TIERS = ("T0", "T1", "T2", "T3")


def _clean_text(value, default=""):
    text = str(value or "").strip()
    return text or default


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = [value]
    return [item for item in values if item not in (None, "")]


def _safe_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _stock_code(candidate):
    text = _clean_text(
        candidate.get("code")
        or candidate.get("stock_code")
        or candidate.get("代码")
        or candidate.get("股票代码")
    ).upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits.zfill(6) if digits else ""


def _stock_name(candidate, stock_code=""):
    return _clean_text(
        candidate.get("name")
        or candidate.get("stock_name")
        or candidate.get("名称")
        or candidate.get("股票"),
        stock_code or "观察对象",
    )


def _candidate_label(candidate):
    code = _stock_code(candidate)
    name = _stock_name(candidate, code)
    if name and code:
        return f"{name}({code})"
    return name or code or "观察对象"


def _normalize_result(value):
    text = _clean_text(value)
    return text if text in CHECK_RESULTS else "数据缺失"


def _account_status(candidate):
    explicit = _clean_text(candidate.get("account_trade_status") or candidate.get("账户状态"))
    if explicit in ("实际可买", "实际不可买"):
        return explicit
    code = _stock_code(candidate)
    latest_price = _safe_float(candidate.get("latest_price") or candidate.get("最新价") or candidate.get("price"))
    available_cash = _safe_float(candidate.get("available_cash") or candidate.get("可用资金") or candidate.get("account_cash"))
    if code.startswith("688") and not candidate.get("can_trade_star_market"):
        return "实际不可买"
    if latest_price > 0 and available_cash > 0 and latest_price * 100 > available_cash:
        return "实际不可买"
    return "实际可买" if latest_price > 0 or available_cash > 0 else "数据缺失"


def _source_pools(candidate):
    pools = _as_list(candidate.get("source_pools") or candidate.get("来源池") or candidate.get("source_pool"))
    return [str(item).strip() for item in pools if str(item).strip()]


def _tier(candidate):
    text = _clean_text(candidate.get("tier") or candidate.get("层级") or candidate.get("action_tier"))
    if text in VALID_TIERS:
        return text
    action_ceiling = _clean_text(candidate.get("action_ceiling") or candidate.get("动作上限"))
    if action_ceiling in ("主买", "补位"):
        return "T0"
    if action_ceiling == "核心观察":
        return "T1"
    if action_ceiling == "修复观察":
        return "T2"
    return "T3"


def _build_check(check_key, label, result, evidence, branch_effect):
    normalized = _normalize_result(result)
    return {
        "check_key": check_key,
        "label": label,
        "result": normalized,
        "evidence": _clean_text(evidence, "数据缺失" if normalized == "数据缺失" else ""),
        "branch_effect": _clean_text(branch_effect),
    }


def _check_from_candidate(candidate, prefix, label):
    return _build_check(
        prefix,
        label,
        candidate.get(f"{prefix}_fit") or candidate.get(f"{prefix}_result"),
        candidate.get(f"{prefix}_evidence"),
        candidate.get(f"{prefix}_branch_effect"),
    )


def _missing_data(candidate, mainline, sector, checks):
    missing = []
    if not _stock_code(candidate):
        missing.append("stock_code")
    if not mainline:
        missing.append("mainline")
    if not sector:
        missing.append("sector")
    if _account_status(candidate) == "数据缺失":
        missing.append("account_context")
    for check in checks:
        if check["result"] == "数据缺失":
            missing.append(check["check_key"])
    return sorted(set(missing))


def _branch_step_for_check(check):
    result = check["result"]
    label = check["label"]
    if result == "数据缺失":
        return f"{label}数据缺失"
    return f"{label}{result}"


def _branch_terminal(tier, account_status, checks):
    if account_status == "实际不可买":
        return "账户不适配，不能进入 T0 新开仓"
    if any(check["result"] == "数据缺失" for check in checks):
        return "关键数据不完整，停止生成动作"
    if tier == "T0":
        return "进入 T0 条件观察"
    if tier == "T1":
        return "进入 T1 主线核心观察"
    if tier == "T2":
        return "进入 T2 次主线或备选观察"
    return "进入 T3 观察线索"


def _visible_summary(tier, checks, account_status):
    positive = [check["label"].replace("条件", "") + check["result"] for check in checks if check["result"] in ("满足", "部分满足")]
    if account_status == "实际不可买":
        positive.append("账户不适配")
    if not positive:
        positive.append("关键数据不完整")
    text = "、".join(positive[:3])
    suffix = {
        "T0": "；条件观察",
        "T1": "；核心观察",
        "T2": "；备选观察",
        "T3": "；线索观察",
    }.get(tier, "；线索观察")
    summary = f"{text}{suffix}"
    return summary[:40]


def build_candidate_trace(candidate):
    candidate = candidate or {}
    code = _stock_code(candidate)
    name = _stock_name(candidate, code)
    tier = _tier(candidate)
    mainline = _clean_text(candidate.get("mainline") or candidate.get("主线"))
    sector = _clean_text(candidate.get("sector") or candidate.get("sector_candidate") or candidate.get("板块"))
    account_status = _account_status(candidate)
    checks = [
        _check_from_candidate(candidate, "market", "市场条件"),
        _check_from_candidate(candidate, "mainline", "主线条件"),
        _check_from_candidate(candidate, "stock_structure", "个股结构"),
    ]
    missing_data = _missing_data(candidate, mainline, sector, checks)
    final_action = _clean_text(candidate.get("final_action") or candidate.get("new_entry_action") or candidate.get("新开仓动作"))
    if missing_data and not final_action:
        final_action = "关键数据不完整，停止生成动作"
    elif not final_action:
        final_action = "不参与，只保留观察"

    key_inputs = [
        {"field": "来源池", "value": "、".join(_source_pools(candidate)) or "未注明", "source": "candidate_context"},
        {"field": "主线/板块", "value": mainline or sector or "未归类", "source": "market_context"},
        {"field": "账户适配", "value": account_status, "source": "account_context"},
    ]
    window = _clean_text(candidate.get("buy_window") or candidate.get("participation_window") or candidate.get("交易窗口"))
    if window:
        key_inputs.append({"field": "交易窗口", "value": window, "source": "time_window_contract"})

    branch_path = [_branch_step_for_check(check) for check in checks]
    branch_path.append(_branch_terminal(tier, account_status, checks))
    branch_path = branch_path[:6]

    return {
        "candidate_id": _clean_text(candidate.get("candidate_id"), f"{code or name}"),
        "stock_code": code,
        "stock_name": name,
        "candidate_label": _candidate_label(candidate),
        "tier": tier,
        "source_pools": _source_pools(candidate),
        "mainline": mainline or "未归类",
        "sector": sector or "未归类",
        "key_inputs": key_inputs,
        "checks": checks,
        "branch_path": branch_path,
        "final_action": final_action,
        "trigger_condition": _clean_text(candidate.get("trigger_condition") or candidate.get("触发条件")),
        "failure_condition": _clean_text(candidate.get("failure_condition") or candidate.get("失效条件") or candidate.get("取关条件")),
        "missing_data": missing_data,
        "visible_summary": _visible_summary(tier, checks, account_status),
    }


def _eliminated_treatment(reason):
    reason = _clean_text(reason, "数据缺失")
    if reason == "账户不适配":
        return "保留市场身份，不进入 T0 新开仓"
    if reason == "数据缺失":
        return "关键数据不完整，停止生成动作"
    if reason == "个股承接不足":
        return "等待重新满足条件"
    return "保留观察，不进入动作分层"


def build_eliminated_summary(items):
    grouped = {}
    for item in list(items or []):
        reason = _clean_text((item or {}).get("reason") or (item or {}).get("淘汰原因"), "数据缺失")
        name = _clean_text((item or {}).get("name") or (item or {}).get("stock_name") or (item or {}).get("股票"), "观察对象")
        bucket = grouped.setdefault(
            reason,
            {"reason": reason, "count": 0, "representatives": [], "treatment": _eliminated_treatment(reason)},
        )
        bucket["count"] += 1
        if name and len(bucket["representatives"]) < 3:
            bucket["representatives"].append(name)
    return list(grouped.values())


def _default_generated_at():
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def build_candidate_trace_artifact_payload(
    *,
    trade_date,
    traces,
    eliminated_summary=None,
    generated_at=None,
    source_report=None,
):
    return {
        "artifact_version": ARTIFACT_VERSION,
        "trade_date": _clean_text(trade_date),
        "generated_at": _clean_text(generated_at) or _default_generated_at(),
        "source_report": dict(source_report or {}),
        "visible_scope": VISIBLE_SCOPE,
        "traces": list(traces or []),
        "eliminated_summary": list(eliminated_summary or []),
    }


__all__ = [
    "ARTIFACT_VERSION",
    "CHECK_RESULTS",
    "VALID_TIERS",
    "VISIBLE_SCOPE",
    "build_candidate_trace",
    "build_candidate_trace_artifact_payload",
    "build_eliminated_summary",
]
```

- [ ] **Step 4: Run trace contract tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_contracts
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add scripts/selection/candidate_trace_contracts.py tests/test_candidate_trace_contracts.py
git commit -m "feat: add candidate trace contract"
```

## Task 2: Attach Trace To Candidate Quality Contracts

**Files:**
- Modify: `scripts/selection/candidate_quality_contracts.py`
- Modify: `tests/test_candidate_quality_contracts.py`

- [ ] **Step 1: Write failing contract integration tests**

Append these tests inside `CandidateQualityContractsTest` in `tests/test_candidate_quality_contracts.py`:

```python
    def test_candidate_quality_contract_includes_trace(self):
        contract = build_candidate_quality_contract(
            {
                "name": "华天科技",
                "code": "002185",
                "tier": "T0",
                "source_pools": ["主线核心候选"],
                "mainline": "半导体",
                "sector": "半导体",
                "market_fit": "部分满足",
                "mainline_fit": "满足",
                "stock_structure_fit": "部分满足",
                "latest_price": 13.2,
                "available_cash": 10000,
                "trigger_condition": "主线承接 + 个股突破或回踩确认",
                "failure_condition": "主线回落或放量不承接",
            },
            action_ceiling="核心观察",
            new_entry_action="09:50-10:10确认，不满足继续不参与",
        )

        trace = contract["trace"]
        self.assertEqual(trace["stock_code"], "002185")
        self.assertEqual(trace["stock_name"], "华天科技")
        self.assertEqual(trace["tier"], "T0")
        self.assertEqual(trace["final_action"], "09:50-10:10确认，不满足继续不参与")
        self.assertEqual(contract["data"]["trace"]["stock_code"], "002185")

    def test_candidate_quality_contract_trace_uses_action_when_candidate_has_no_final_action(self):
        contract = evaluate_candidate_quality_sample_contract(
            {
                "name": "宏和科技",
                "code": "603256",
                "tier": "T1",
                "source_pools": ["主线核心候选"],
                "mainline": "玻璃基板",
                "sector": "玻璃基板",
                "market_fit": "满足",
                "mainline_fit": "满足",
                "stock_structure_fit": "部分满足",
                "quality_role": "核心观察",
                "latest_price": 172.87,
                "available_cash": 10000,
            }
        )

        self.assertEqual(contract["trace"]["final_action"], "账户条件不适配，只观察强度，不参与")
        self.assertIn("账户不适配，不能进入 T0 新开仓", contract["trace"]["branch_path"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_contracts.CandidateQualityContractsTest.test_candidate_quality_contract_includes_trace tests.test_candidate_quality_contracts.CandidateQualityContractsTest.test_candidate_quality_contract_trace_uses_action_when_candidate_has_no_final_action
```

Expected:

```text
KeyError: 'trace'
```

- [ ] **Step 3: Attach trace in candidate quality contract**

Modify `scripts/selection/candidate_quality_contracts.py`.

Add import near the top:

```python
from selection.candidate_trace_contracts import build_candidate_trace
```

Inside `build_candidate_quality_contract`, immediately before `return { ... }`, add:

```python
    trace_candidate = {
        **candidate,
        "action_ceiling": action_ceiling,
        "new_entry_action": new_entry_action,
        "final_action": candidate.get("final_action") or new_entry_action,
        "trigger_condition": candidate.get("trigger_condition") or worst_case_plan.get("触发条件", ""),
        "failure_condition": candidate.get("failure_condition") or visible_row["取关条件"],
    }
    trace = build_candidate_trace(trace_candidate)
```

Then update the returned dictionary to include:

```python
        "trace": trace,
```

and inside `"data": { ... }`, include:

```python
            "trace": trace,
```

- [ ] **Step 4: Run focused integration tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_contracts.CandidateQualityContractsTest.test_candidate_quality_contract_includes_trace tests.test_candidate_quality_contracts.CandidateQualityContractsTest.test_candidate_quality_contract_trace_uses_action_when_candidate_has_no_final_action
```

Expected:

```text
OK
```

- [ ] **Step 5: Run full candidate quality contract tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_contracts
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add scripts/selection/candidate_quality_contracts.py tests/test_candidate_quality_contracts.py
git commit -m "feat: attach traces to candidate quality contracts"
```

## Task 3: Render Candidate Trace Tables

**Files:**
- Modify: `scripts/report/candidate_quality_renderer.py`
- Modify: `tests/test_candidate_quality_renderer.py`

- [ ] **Step 1: Write failing renderer tests**

Append these tests inside `CandidateQualityRendererTest` in `tests/test_candidate_quality_renderer.py`:

```python
    def test_renderer_outputs_candidate_trace_tables(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")
        contracts = [
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "华天科技",
                    "code": "002185",
                    "tier": "T0",
                    "source_pools": ["主线核心候选"],
                    "mainline": "半导体",
                    "sector": "半导体",
                    "market_fit": "部分满足",
                    "mainline_fit": "满足",
                    "stock_structure_fit": "部分满足",
                    "latest_price": 13.2,
                    "available_cash": 10000,
                    "final_action": "09:50-10:10确认，不满足继续不参与",
                    "failure_condition": "主线回落或放量不承接",
                }
            ),
            evaluate_candidate_quality_sample_contract(
                {
                    "name": "步步高",
                    "code": "002251",
                    "tier": "T3",
                    "source_pools": ["异动线索"],
                    "mainline": "消费",
                    "sector": "消费",
                    "market_fit": "未满足",
                    "mainline_fit": "未满足",
                    "stock_structure_fit": "部分满足",
                    "final_action": "不参与，只记录观察线索",
                }
            ),
        ]

        markdown = render_candidate_quality_section(panel, contracts, render_trace_tables=True)

        self.assertIn("### 候选选股轨迹", markdown)
        self.assertIn("| 层级 | 候选 | 主线/板块 | 为什么进入这一层 | 卡点 | 明日动作 |", markdown)
        self.assertIn("| T0 | 华天科技(002185) | 半导体 |", markdown)
        self.assertNotIn("| T3 | 步步高(002251) | 消费 | 为什么进入这一层 |", markdown)
        self.assertIn("### 候选选股轨迹明细", markdown)
        self.assertIn("| 层级 | 候选 | 来源池 | 主线/板块 | 关键输入 | 满足条件 | 未满足/缺失 | 分支结果 | 明日动作 | 失效条件 |", markdown)
        self.assertIn("| T3 | 步步高(002251) | 异动线索 | 消费 |", markdown)

    def test_renderer_outputs_eliminated_summary(self):
        panel = build_daily_quality_decision_panel(market_emotion_label="主线活跃")

        markdown = render_candidate_quality_section(
            panel,
            [],
            eliminated_summary=[
                {"reason": "主线不匹配", "count": 2, "representatives": ["大众公用", "红星发展"], "treatment": "保留观察，不进入动作分层"}
            ],
            render_trace_tables=True,
        )

        self.assertIn("### 未进入分层原因统计", markdown)
        self.assertIn("| 主线不匹配 | 2 | 大众公用、红星发展 | 保留观察，不进入动作分层 |", markdown)
```

- [ ] **Step 2: Run renderer tests to verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer.CandidateQualityRendererTest.test_renderer_outputs_candidate_trace_tables tests.test_candidate_quality_renderer.CandidateQualityRendererTest.test_renderer_outputs_eliminated_summary
```

Expected:

```text
TypeError: render_candidate_quality_section() got an unexpected keyword argument 'render_trace_tables'
```

- [ ] **Step 3: Implement trace table rendering**

Modify `scripts/report/candidate_quality_renderer.py`.

Add constants after `SINGLE_STOCK_FIELDS`:

```python
COMPACT_TRACE_FIELDS = ["层级", "候选", "主线/板块", "为什么进入这一层", "卡点", "明日动作"]
FULL_TRACE_FIELDS = ["层级", "候选", "来源池", "主线/板块", "关键输入", "满足条件", "未满足/缺失", "分支结果", "明日动作", "失效条件"]
```

Add helper functions before `render_candidate_quality_section`:

```python
def _join_trace_items(items, *, field=None):
    texts = []
    for item in list(items or []):
        if isinstance(item, dict):
            if field:
                value = item.get(field)
            else:
                value = item.get("value") or item.get("label") or item.get("evidence")
            if value not in (None, ""):
                texts.append(str(value))
        elif item not in (None, ""):
            texts.append(str(item))
    return "、".join(texts)


def _trace_label(trace):
    name = _cell((trace or {}).get("stock_name", ""))
    code = _cell((trace or {}).get("stock_code", ""))
    if name and code:
        return f"{name}({code})"
    return _cell((trace or {}).get("candidate_label") or name or code or "观察对象")


def _trace_mainline_sector(trace):
    mainline = _cell((trace or {}).get("mainline", ""))
    sector = _cell((trace or {}).get("sector", ""))
    if mainline and sector and mainline != sector:
        return f"{mainline}/{sector}"
    return mainline or sector or "未归类"


def _trace_check_text(trace, wanted_results):
    texts = []
    for check in list((trace or {}).get("checks") or []):
        if check.get("result") in wanted_results:
            texts.append(f"{check.get('label')}：{check.get('result')}")
    return "；".join(texts)


def _compact_trace_row(trace):
    return {
        "层级": _cell((trace or {}).get("tier", "")),
        "候选": _trace_label(trace),
        "主线/板块": _trace_mainline_sector(trace),
        "为什么进入这一层": _cell((trace or {}).get("visible_summary", "")),
        "卡点": _trace_check_text(trace, {"部分满足", "未满足", "数据缺失"}),
        "明日动作": _cell((trace or {}).get("final_action", "")),
    }


def _full_trace_row(trace):
    return {
        "层级": _cell((trace or {}).get("tier", "")),
        "候选": _trace_label(trace),
        "来源池": _cell("、".join((trace or {}).get("source_pools") or [])),
        "主线/板块": _trace_mainline_sector(trace),
        "关键输入": _cell(_join_trace_items((trace or {}).get("key_inputs"))),
        "满足条件": _cell(_trace_check_text(trace, {"满足", "部分满足"})),
        "未满足/缺失": _cell(_trace_check_text(trace, {"未满足", "数据缺失"})),
        "分支结果": _cell(" -> ".join((trace or {}).get("branch_path") or [])),
        "明日动作": _cell((trace or {}).get("final_action", "")),
        "失效条件": _cell((trace or {}).get("failure_condition", "")),
    }


def _render_table_from_rows(title, fields, rows, heading_level):
    lines = [_heading(heading_level, title), ""]
    if not rows:
        lines.append("暂无候选选股轨迹。")
        return lines
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("|" + "|".join(["------"] * len(fields)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(_cell(row.get(field, "")) for field in fields) + " |")
    return lines


def _render_trace_tables(contracts, heading_level=3):
    traces = [(contract or {}).get("trace") for contract in list(contracts or []) if (contract or {}).get("trace")]
    compact_traces = [trace for trace in traces if trace.get("tier") in ("T0", "T1")]
    lines = _render_table_from_rows(
        "候选选股轨迹",
        COMPACT_TRACE_FIELDS,
        [_compact_trace_row(trace) for trace in compact_traces],
        heading_level,
    )
    lines.append("")
    lines.extend(
        _render_table_from_rows(
            "候选选股轨迹明细",
            FULL_TRACE_FIELDS,
            [_full_trace_row(trace) for trace in traces],
            heading_level,
        )
    )
    return lines


def _render_eliminated_summary(eliminated_summary, heading_level=3):
    rows = list(eliminated_summary or [])
    if not rows:
        return []
    fields = ["淘汰原因", "数量", "代表对象", "处理"]
    lines = [_heading(heading_level, "未进入分层原因统计"), ""]
    lines.append("| " + " | ".join(fields) + " |")
    lines.append("|" + "|".join(["------"] * len(fields)) + "|")
    for row in rows:
        rendered = {
            "淘汰原因": row.get("reason", ""),
            "数量": row.get("count", ""),
            "代表对象": "、".join(row.get("representatives") or []),
            "处理": row.get("treatment", ""),
        }
        lines.append("| " + " | ".join(_cell(rendered.get(field, "")) for field in fields) + " |")
    return lines
```

Change the function signature:

```python
def render_candidate_quality_section(
    panel,
    candidate_contracts,
    heading_level=2,
    table_fields=None,
    *,
    render_trace_tables=False,
    eliminated_summary=None,
):
```

Inside `render_candidate_quality_section`, after rendering the candidate table and before single-stock details, insert:

```python
    if render_trace_tables:
        lines.append("")
        lines.extend(_render_trace_tables(contracts, heading_level + 1))
        eliminated_lines = _render_eliminated_summary(eliminated_summary, heading_level + 1)
        if eliminated_lines:
            lines.append("")
            lines.extend(eliminated_lines)
```

Update `__all__`:

```python
__all__ = ["COMPACT_CANDIDATE_TABLE_FIELDS", "render_candidate_quality_section"]
```

Keep `__all__` unchanged if it already matches this.

- [ ] **Step 4: Run renderer focused tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer.CandidateQualityRendererTest.test_renderer_outputs_candidate_trace_tables tests.test_candidate_quality_renderer.CandidateQualityRendererTest.test_renderer_outputs_eliminated_summary
```

Expected:

```text
OK
```

- [ ] **Step 5: Run full renderer tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add scripts/report/candidate_quality_renderer.py tests/test_candidate_quality_renderer.py
git commit -m "feat: render candidate selection traces"
```

## Task 4: Action Plan Integration And Exports

**Files:**
- Modify: `scripts/report/action_plan_nodes.py`
- Modify: `tests/test_action_plan_renderer.py`

- [ ] **Step 1: Write failing action plan integration test**

Append this test inside the existing test class in `tests/test_action_plan_renderer.py`:

```python
    def test_candidate_quality_node_can_render_and_export_candidate_traces(self):
        lines = build_action_plan_candidate_quality_node(
            {
                "candidate_quality_panel_fields": {
                    "market_emotion_label": "主线活跃",
                    "daily_new_entry_limit": 1,
                },
                "candidate_quality_samples": [
                    {
                        "name": "华天科技",
                        "code": "002185",
                        "tier": "T0",
                        "source_pools": ["主线核心候选"],
                        "mainline": "半导体",
                        "sector": "半导体",
                        "market_fit": "部分满足",
                        "mainline_fit": "满足",
                        "stock_structure_fit": "部分满足",
                        "latest_price": 13.2,
                        "available_cash": 10000,
                        "final_action": "09:50-10:10确认，不满足继续不参与",
                    }
                ],
                "candidate_trace_eliminated_items": [
                    {"name": "大众公用", "reason": "主线不匹配"},
                ],
                "render_candidate_trace_tables": True,
                "enabled_node_keys": ["candidate_quality"],
            }
        )

        rendered = "\n".join(lines["lines"])
        self.assertIn("候选选股轨迹", rendered)
        self.assertIn("未进入分层原因统计", rendered)
        self.assertEqual(lines["exports"]["candidate_traces"][0]["stock_code"], "002185")
        self.assertEqual(lines["exports"]["candidate_trace_eliminated_summary"][0]["reason"], "主线不匹配")
```

If `tests/test_action_plan_renderer.py` imports only `render_action_plan_section`, add this import near the top:

```python
from report.action_plan_nodes import build_action_plan_candidate_quality_node
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_action_plan_renderer.ActionPlanRendererTest.test_candidate_quality_node_can_render_and_export_candidate_traces
```

Expected:

```text
AssertionError: '候选选股轨迹' not found
```

or:

```text
KeyError: 'candidate_traces'
```

- [ ] **Step 3: Implement action-plan trace rendering and exports**

Modify `scripts/report/action_plan_nodes.py`.

Add import:

```python
from selection.candidate_trace_contracts import build_eliminated_summary
```

Inside `build_action_plan_candidate_quality_node`, after materializing `contracts`, add:

```python
    eliminated_summary = context.get("candidate_trace_eliminated_summary")
    if eliminated_summary is None:
        eliminated_summary = build_eliminated_summary(context.get("candidate_trace_eliminated_items") or [])
    render_trace_tables = bool(context.get("render_candidate_trace_tables"))
    traces = [
        contract.get("trace")
        for contract in contracts
        if isinstance(contract, dict) and contract.get("trace")
    ]
```

Update the `render_candidate_quality_section` call:

```python
        "lines": render_candidate_quality_section(
            panel,
            contracts,
            heading_level=heading_level,
            table_fields=COMPACT_CANDIDATE_TABLE_FIELDS,
            render_trace_tables=render_trace_tables,
            eliminated_summary=eliminated_summary,
        ).splitlines(),
        "exports": {
            "candidate_traces": traces,
            "candidate_trace_eliminated_summary": eliminated_summary,
        },
```

Keep the existing early return when `panel` is missing.

- [ ] **Step 4: Run action plan focused test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_action_plan_renderer.ActionPlanRendererTest.test_candidate_quality_node_can_render_and_export_candidate_traces
```

Expected:

```text
OK
```

- [ ] **Step 5: Run full action plan renderer tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_action_plan_renderer
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add scripts/report/action_plan_nodes.py tests/test_action_plan_renderer.py
git commit -m "feat: export candidate selection traces"
```

## Task 5: Candidate Trace Artifact Writer

**Files:**
- Create: `scripts/report/candidate_trace_artifacts.py`
- Test: `tests/test_candidate_trace_artifacts.py`

- [ ] **Step 1: Write failing artifact writer tests**

Create `tests/test_candidate_trace_artifacts.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.candidate_trace_artifacts import write_candidate_trace_artifact
from selection.candidate_trace_contracts import build_candidate_trace


class CandidateTraceArtifactsTest(unittest.TestCase):
    def test_write_candidate_trace_artifact(self):
        trace = build_candidate_trace({"name": "华天科技", "code": "002185", "tier": "T0"})
        with tempfile.TemporaryDirectory() as tempdir:
            result = write_candidate_trace_artifact(
                trade_date="2026-05-26",
                traces=[trace],
                eliminated_summary=[
                    {"reason": "主线不匹配", "count": 1, "representatives": ["大众公用"], "treatment": "保留观察，不进入动作分层"}
                ],
                root_dir=Path(tempdir),
                generated_at="2026-05-27T00:00:00+08:00",
                source_report={"path": "reports/2026-05-26_A股日报_完整版.md", "variant": "full"},
            )

            path = Path(result["artifact_path"])
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["trade_date"], "2026-05-26")
            self.assertEqual(payload["traces"][0]["stock_code"], "002185")
            self.assertEqual(result["trace_count"], 1)
            self.assertEqual(result["eliminated_group_count"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_artifacts
```

Expected:

```text
ModuleNotFoundError: No module named 'report.candidate_trace_artifacts'
```

- [ ] **Step 3: Implement artifact writer**

Create `scripts/report/candidate_trace_artifacts.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from selection.candidate_trace_contracts import build_candidate_trace_artifact_payload


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_candidate_trace_artifact(
    *,
    trade_date,
    traces,
    eliminated_summary=None,
    root_dir=".",
    generated_at=None,
    source_report=None,
):
    root = Path(root_dir)
    payload = build_candidate_trace_artifact_payload(
        trade_date=trade_date,
        traces=traces,
        eliminated_summary=eliminated_summary or [],
        generated_at=generated_at,
        source_report=source_report or {},
    )
    artifact_path = root / "data" / "candidate-traces" / f"{trade_date}.json"
    _write_json(artifact_path, payload)
    return {
        "artifact_path": str(artifact_path),
        "trace_count": len(payload.get("traces") or []),
        "eliminated_group_count": len(payload.get("eliminated_summary") or []),
        "payload": payload,
    }


__all__ = ["write_candidate_trace_artifact"]
```

- [ ] **Step 4: Run artifact writer tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_artifacts
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add scripts/report/candidate_trace_artifacts.py tests/test_candidate_trace_artifacts.py
git commit -m "feat: write candidate trace artifacts"
```

## Task 6: Regression Verification

**Files:**
- No new files expected.
- May modify tests only if earlier tasks revealed exact assertion updates needed.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_candidate_trace_contracts \
  tests.test_candidate_trace_artifacts \
  tests.test_candidate_quality_contracts \
  tests.test_candidate_quality_renderer \
  tests.test_action_plan_renderer
```

Expected:

```text
OK
```

- [ ] **Step 2: Run report runtime smoke tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime
```

Expected:

```text
OK
```

- [ ] **Step 3: Search for disallowed user-visible wording introduced by this feature**

Run:

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path

terms = []
source = Path("wiki/交易思想/日报术语契约.md").read_text(encoding="utf-8")
for line in source.splitlines():
    text = line.strip()
    if text.startswith("- `") and text.endswith("`"):
        terms.append(text.strip("- `"))

paths = [
    Path("scripts/selection/candidate_trace_contracts.py"),
    Path("scripts/report/candidate_quality_renderer.py"),
    Path("scripts/report/action_plan_nodes.py"),
    Path("scripts/report/candidate_trace_artifacts.py"),
    Path("tests/test_candidate_trace_contracts.py"),
    Path("tests/test_candidate_quality_renderer.py"),
    Path("tests/test_action_plan_renderer.py"),
    Path("tests/test_candidate_trace_artifacts.py"),
]
hits = []
for path in paths:
    if not path.exists():
        continue
    text = path.read_text(encoding="utf-8")
    for term in terms:
        if term and term in text:
            hits.append(f"{path}: {term}")
if hits:
    raise SystemExit("\n".join(hits))
PY
```

Expected: no matches.

- [ ] **Step 4: Confirm git diff only contains intended files**

Run:

```bash
git status --short scripts/selection/candidate_trace_contracts.py scripts/selection/candidate_quality_contracts.py scripts/report/candidate_quality_renderer.py scripts/report/action_plan_nodes.py scripts/report/candidate_trace_artifacts.py tests/test_candidate_trace_contracts.py tests/test_candidate_quality_contracts.py tests/test_candidate_quality_renderer.py tests/test_action_plan_renderer.py tests/test_candidate_trace_artifacts.py
```

Expected: either clean, or only intended files from this plan.

- [ ] **Step 5: Final commit if verification changed files**

If Step 4 shows modified intended files, run:

```bash
git add scripts/selection/candidate_trace_contracts.py scripts/selection/candidate_quality_contracts.py scripts/report/candidate_quality_renderer.py scripts/report/action_plan_nodes.py scripts/report/candidate_trace_artifacts.py tests/test_candidate_trace_contracts.py tests/test_candidate_quality_contracts.py tests/test_candidate_quality_renderer.py tests/test_action_plan_renderer.py tests/test_candidate_trace_artifacts.py
git commit -m "test: verify candidate selection traces"
```

Expected: commit succeeds or there is nothing to commit.

## Implementation Notes

- The repo has many unrelated modified files. Do not stage or revert unrelated changes.
- Use `cat`, `head`, `sed`, and `rg` for file reads.
- Use `apply_patch` for edits.
- Keep all user-visible wording in trading language: `条件`, `资格`, `参与`, `不参与`, `关键数据不完整`.
- Do not expand this plan into a new ranking engine.
