# Daily Report Two-Layer Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first compatible implementation of the two-layer daily report: front decision layer plus derivation audit layer, with `明日执行对象` and B-level execution conditions as the canonical reader-facing contract.

**Architecture:** Add one focused compatibility payload builder under `scripts/report/`, then render a new front decision section and Step audit summaries from that payload. Keep existing data collectors and scoring internals intact; wire the payload into `scripts/report/runtime.py` after execution-stage context and final target resolution are available. Extend acceptance checks so process evidence cannot contradict the front execution object.

**Tech Stack:** Python 3.14 via `.generated/venv-py314/bin/python3.14`, existing `unittest` suite, existing report runtime and acceptance audit modules.

---

## File Structure

- Create `scripts/report/two_layer_decision_payload.py`
  - Responsibility: build a canonical payload from existing runtime dictionaries.
  - Exports:
    - `build_two_layer_decision_payload(...)`
    - `render_front_decision_layer(payload)`
    - `render_derivation_audit_layer(payload)`
    - small helper functions for stock labels, money bucket selection, and Step audit rows.

- Modify `scripts/report/runtime.py`
  - Import the new builder/renderer.
  - Build and store `two_layer_decision_payload` after final target resolution and position decision are known.
  - Insert the new front decision layer before the old account-advice/front evidence block.
  - Append the Step audit layer near the execution-chain appendix.

- Modify `scripts/report/report_acceptance_audit.py`
  - Extract `明日执行对象`.
  - Reject reports where a concrete execution object exists later but the front layer is missing or mismatched.
  - Reject 50% execution without visible conditions.

- Add `tests/test_two_layer_decision_payload.py`
  - Unit tests for payload construction, B-level conditions, money bucket selection, and Step audit rendering.

- Modify `tests/test_report_runtime.py`
  - Runtime integration tests for the new front decision layer and Step audit layer.

- Modify `tests/test_report_acceptance_audit.py`
  - Audit tests for missing/mismatched `明日执行对象` and missing 50% conditions.

## Task 1: Payload Builder Unit Tests

**Files:**
- Create: `tests/test_two_layer_decision_payload.py`
- Create later in this task: `scripts/report/two_layer_decision_payload.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_two_layer_decision_payload.py` with:

```python
import unittest

from report.two_layer_decision_payload import (
    build_two_layer_decision_payload,
    render_front_decision_layer,
    render_derivation_audit_layer,
)


class TwoLayerDecisionPayloadTest(unittest.TestCase):
    def test_builds_conditional_execution_object_with_b_level_conditions(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "display_target": {"name": "豫能控股", "code": "001896", "sector": "电力"},
            },
            position_decision={
                "target_position_pct": 50,
                "final_action": "条件满足才50%条件执行；不满足回到0%",
            },
            execution_stage_context={
                "market_state_snapshot": {"market_state": "退潮"},
                "mainline_name": "电力",
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                        {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    ]
                },
                "step3_bundle": {
                    "focus_group": [{"name": "豫能控股", "code": "001896"}],
                    "delete_group": [],
                    "keep_group": [],
                },
                "executable_stocks": [{"name": "豫能控股", "code": "001896"}],
                "waiting_stocks": [],
                "rejected_stocks": [],
            },
        )

        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "001896")
        self.assertEqual(payload["front_decision"]["execution_identity"], "明日执行对象")
        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
        self.assertEqual(payload["front_decision"]["if_fail"], "不参与")
        self.assertIn("low_open_acceptance", payload["b_level_conditions"])
        self.assertIn("active_attack", payload["b_level_conditions"])

    def test_money_bucket_uses_large_core_threshold_when_amount_is_large(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {
                    "name": "工业富联",
                    "code": "601138",
                    "sector": "AI算力基础设施",
                    "market_value": 900000000000,
                    "turnover_amount": 18000000000,
                }
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        active_attack = payload["b_level_conditions"]["active_attack"]
        self.assertEqual(active_attack["money_bucket"], "大市值或高成交核心")
        self.assertIn("1亿+", active_attack["money_confirmation"])

    def test_render_front_decision_layer_uses_execution_object_not_passive_wording(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"}
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={},
        )

        text = "\n".join(render_front_decision_layer(payload))

        self.assertIn("## 明日执行结论", text)
        self.assertIn("| 明日执行对象 | 豫能控股(001896) |", text)
        self.assertIn("## 50%执行条件", text)
        self.assertIn("低开承接型", text)
        self.assertIn("主动进攻型", text)
        self.assertNotIn("观察对象", text)

    def test_render_derivation_audit_layer_uses_required_step_template(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "watch_target": {"name": "豫能控股", "code": "001896", "sector": "电力"}
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688"},
                        {"name": "豫能控股", "code": "001896"},
                    ]
                },
                "step3_bundle": {"focus_group": [{"name": "豫能控股", "code": "001896"}]},
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("## 推导审计层", text)
        self.assertIn("### Step 2：主方向与候选收缩", text)
        self.assertIn("#### 输入数据", text)
        self.assertIn("#### 本步判断", text)
        self.assertIn("#### 保留与淘汰", text)
        self.assertIn("#### 传给下一步", text)
        self.assertIn("#### 本步不能推出什么", text)
        self.assertIn("豫能控股(001896)", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload
```

Expected: import failure for `report.two_layer_decision_payload`.

- [ ] **Step 3: Create minimal payload implementation**

Create `scripts/report/two_layer_decision_payload.py` with:

```python
from __future__ import annotations


def _clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text or default


def _normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _stock_payload(value):
    if not isinstance(value, dict):
        return {}
    name = _clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = _normalize_stock_code(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    if not (name or code):
        return {}
    payload = {"name": name, "code": code}
    sector = _clean_text(value.get("sector") or value.get("sector_name") or value.get("industry") or value.get("板块"))
    if sector:
        payload["sector"] = sector
    for numeric_key in ("market_value", "turnover_amount", "amount"):
        if numeric_key in value:
            payload[numeric_key] = value.get(numeric_key)
    return payload


def _stock_label(value):
    payload = _stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _safe_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").replace("亿", "").strip())
    except (TypeError, ValueError):
        return default


def _first_stock(*values):
    for value in values:
        payload = _stock_payload(value)
        if payload:
            return payload
    return {}


def _position_pct(position_decision):
    position_decision = position_decision if isinstance(position_decision, dict) else {}
    for key in ("target_position_pct", "position_pct"):
        if key not in position_decision:
            continue
        try:
            return int(float(str(position_decision.get(key)).replace("%", "").strip()))
        except (TypeError, ValueError):
            continue
    return 0


def _money_bucket(target):
    target = target if isinstance(target, dict) else {}
    market_value = _safe_float(target.get("market_value"))
    turnover_amount = _safe_float(target.get("turnover_amount") or target.get("amount"))
    if market_value >= 300000000000 or turnover_amount >= 10000000000:
        return {
            "money_bucket": "大市值或高成交核心",
            "money_confirmation": "分时大单净流入1亿+，并保持VWAP上方",
        }
    return {
        "money_bucket": "小中盘活跃股",
        "money_confirmation": "分时大单净流入3000w-5000w，并保持VWAP上方",
    }


def _build_b_level_conditions(target):
    active_attack = _money_bucket(target)
    active_attack.update(
        {
            "trigger": "主动进攻型",
            "window": "09:30-09:35或09:50-10:10",
            "price_action": "开盘直线进攻，不快速冲高回落",
            "intraday_hold": "VWAP上方保持，短暂震荡后要快速收回",
            "action": "50%条件执行",
        }
    )
    return {
        "low_open_acceptance": {
            "trigger": "低开承接型",
            "window": "09:50-10:10",
            "daily_structure": "靠近MA5、不有效跌破MA5，或跌破后快速收回MA5",
            "intraday_reclaim": "收回VWAP或0轴并能站住",
            "action": "50%条件执行",
        },
        "active_attack": active_attack,
        "invalidations": [
            "MA5未收回",
            "VWAP/0轴未收回",
            "资金确认不足",
            "市场或相关方向明显走弱",
        ],
    }


def _process_candidates_from_context(execution_stage_context):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    candidates = []
    for key in ("core_stocks", "secondary_stocks", "crossline_observation_stocks", "gem_observation_stocks"):
        for item in bundle.get(key, []) or []:
            payload = _stock_payload(item)
            if payload:
                candidates.append(payload)
    return candidates


def _step_payloads(target, execution_stage_context):
    target_label = _stock_label(target)
    candidates = _process_candidates_from_context(execution_stage_context)
    candidate_labels = [_stock_label(item) for item in candidates if _stock_label(item) != "暂无"]
    rejected = [label for label in candidate_labels if label != target_label]
    return [
        {
            "step": "Step 0",
            "title": "市场底色",
            "input_summary": ["指数涨跌、涨跌家数、成交额趋势、涨停跌停扩散"],
            "judgement": "判断是否允许考虑50%条件执行",
            "kept": [],
            "rejected": [],
            "passes_forward": "可等待50%执行条件",
            "cannot_conclude": "本步不能选出执行对象",
        },
        {
            "step": "Step 1",
            "title": "候选池",
            "input_summary": ["热榜、涨停池、盘中异动、板块与tag证据、近期龙头记忆"],
            "judgement": "形成过程候选，不生成最终身份",
            "kept": candidate_labels,
            "rejected": [],
            "passes_forward": "过程候选进入主方向收缩",
            "cannot_conclude": "本步不能把候选直接升级为明日执行对象",
        },
        {
            "step": "Step 2",
            "title": "主方向与候选收缩",
            "input_summary": ["主方向证据、板块核心、候选质量、跨方向证据"],
            "judgement": f"{target_label}作为条件执行对象继续准备50%执行条件",
            "kept": [target_label] if target_label != "暂无" else [],
            "rejected": rejected,
            "passes_forward": f"条件执行对象：{target_label}",
            "cannot_conclude": "不能推出无条件买入",
        },
        {
            "step": "Step 3",
            "title": "风险复核",
            "input_summary": ["烂板/炸板、板块走弱、A杀或结构破坏、跌停扩散、关键数据缺失"],
            "judgement": f"{target_label}继续保留为条件执行对象",
            "kept": [target_label] if target_label != "暂无" else [],
            "rejected": [],
            "passes_forward": f"{target_label}进入50%条件执行计划",
            "cannot_conclude": "本步不能引入新的执行对象",
        },
        {
            "step": "Step 4",
            "title": "50%条件执行计划",
            "input_summary": ["MA5位置、VWAP/0轴、分时大单净流入分层、市场和方向确认"],
            "judgement": "生成低开承接型和主动进攻型两条触发路径",
            "kept": [target_label] if target_label != "暂无" else [],
            "rejected": [],
            "passes_forward": "50%执行条件同步到前台",
            "cannot_conclude": "条件未出现前不能执行",
        },
        {
            "step": "Step 5",
            "title": "最终一致性",
            "input_summary": ["最终对象、50%执行条件、账户约束、旧仓优先级"],
            "judgement": "同步前台、行动计划、候选质量和附录路径",
            "kept": [target_label] if target_label != "暂无" else [],
            "rejected": [],
            "passes_forward": "生成最终前台决策",
            "cannot_conclude": "不能重新打开候选选择",
        },
    ]


def build_two_layer_decision_payload(
    *,
    target_date="",
    final_target_resolution=None,
    position_decision=None,
    execution_stage_context=None,
):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    position_decision = position_decision if isinstance(position_decision, dict) else {}
    target = _first_stock(
        resolution.get("display_target"),
        resolution.get("watch_target"),
        resolution.get("new_entry_target"),
        resolution.get("process_target"),
    )
    pct = _position_pct(position_decision)
    position_plan = "50%条件执行" if pct > 0 or target else "0%不参与"
    if not target:
        position_plan = "0%不参与"
    payload = {
        "target_date": _clean_text(target_date),
        "front_decision": {
            "position_plan": position_plan,
            "position_pct": 50 if position_plan == "50%条件执行" else 0,
            "execution_object": target,
            "execution_identity": "明日执行对象" if target else "无明日执行对象",
            "if_fail": "不参与",
        },
        "b_level_conditions": _build_b_level_conditions(target),
    }
    payload["derivation_steps"] = _step_payloads(target, execution_stage_context)
    return payload


def render_front_decision_layer(payload):
    payload = payload if isinstance(payload, dict) else {}
    front = payload.get("front_decision") if isinstance(payload.get("front_decision"), dict) else {}
    target = front.get("execution_object") if isinstance(front.get("execution_object"), dict) else {}
    target_label = _stock_label(target)
    conditions = payload.get("b_level_conditions") if isinstance(payload.get("b_level_conditions"), dict) else {}
    low_open = conditions.get("low_open_acceptance") if isinstance(conditions.get("low_open_acceptance"), dict) else {}
    active = conditions.get("active_attack") if isinstance(conditions.get("active_attack"), dict) else {}
    lines = [
        "## 明日执行结论",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 明日仓位 | 条件满足才{front.get('position_plan') or '50%条件执行'}；不满足回到0% |",
        f"| 明日执行对象 | {target_label} |",
        "| 执行性质 | 50%条件执行，约50%仓位 |",
        f"| 不满足条件 | {front.get('if_fail') or '不参与'} |",
        "",
        "## 50%执行条件",
        "| 触发类型 | 必须满足 | 窗口 | 动作 |",
        "|----------|----------|------|------|",
        "| 低开承接型 | {daily}；{intraday} | {window} | {action} |".format(
            daily=low_open.get("daily_structure") or "靠近MA5或快速收回MA5",
            intraday=low_open.get("intraday_reclaim") or "收回VWAP或0轴",
            window=low_open.get("window") or "09:50-10:10",
            action=low_open.get("action") or "50%条件执行",
        ),
        "| 主动进攻型 | {price}；{money}；{hold} | {window} | {action} |".format(
            price=active.get("price_action") or "开盘直线进攻",
            money=active.get("money_confirmation") or "分时大单净流入达标",
            hold=active.get("intraday_hold") or "VWAP上方保持",
            window=active.get("window") or "09:30-09:35或09:50-10:10",
            action=active.get("action") or "50%条件执行",
        ),
        "",
        "## 不执行条件",
    ]
    for item in conditions.get("invalidations", []) or []:
        lines.append(f"- {item}")
    return lines


def render_derivation_audit_layer(payload):
    payload = payload if isinstance(payload, dict) else {}
    lines = ["## 推导审计层"]
    for step in payload.get("derivation_steps", []) or []:
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                "",
                f"### {step.get('step')}：{step.get('title')}",
                "#### 输入数据",
            ]
        )
        for item in step.get("input_summary", []) or []:
            lines.append(f"- {item}")
        lines.extend(["#### 本步判断", f"- {step.get('judgement') or '-'}", "#### 保留与淘汰"])
        kept = "、".join(step.get("kept", []) or []) or "无"
        rejected = "、".join(step.get("rejected", []) or []) or "无"
        lines.append(f"- 保留：{kept}")
        lines.append(f"- 淘汰：{rejected}")
        lines.extend(["#### 传给下一步", f"- {step.get('passes_forward') or '无'}"])
        lines.extend(["#### 本步不能推出什么", f"- {step.get('cannot_conclude') or '-'}"])
    return lines
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add scripts/report/two_layer_decision_payload.py tests/test_two_layer_decision_payload.py
git commit -m "feat(report): add two-layer decision payload"
```

## Task 2: Runtime Integration

**Files:**
- Modify: `scripts/report/runtime.py`
- Modify: `tests/test_report_runtime.py`

- [ ] **Step 1: Add failing runtime integration test**

Add this test to `tests/test_report_runtime.py` near the existing final-target runtime tests:

```python
    def test_runtime_renders_two_layer_front_decision_before_old_account_advice(self):
        captured = {}

        def _run_execution_stages(stage_specs, stage_context=None, stage_lookup=None):
            context = {
                "market_state_snapshot": {"market_state": "退潮"},
                "mainline_name": "电力",
                "position_decision": {"target_position_pct": 50, "final_action": "条件满足才50%条件执行；不满足回到0%"},
                "selected_position_candidate": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {"name": "上海石化", "code": "600688", "sector": "炼化及贸"},
                        {"name": "豫能控股", "code": "001896", "sector": "电力"},
                    ]
                },
                "step3_bundle": {"focus_group": [{"name": "豫能控股", "code": "001896"}]},
                "executable_stocks": [{"name": "豫能控股", "code": "001896"}],
                "market_research_snapshot": {},
            }
            captured["stage_context"] = context
            return {"lines": [], "module_logs": [], "context": context}

        helpers = self._helpers(
            _run_execution_stages=_run_execution_stages,
            run_report_tail_summary=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_strategy_performance_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
            run_execution_appendix_tail=lambda payload: {"value": {"lines": [], "module_logs": [], "exports": {}}},
        )

        data = {
            "target_date": "2026-06-04",
            "best_stock": {"name": "豫能控股", "code": "001896", "sector": "电力"},
        }
        result = report_runtime.render_markdown_report_runtime(
            data,
            "2026-06-04",
            helpers=helpers,
            config={},
        )
        report = result["report"]

        self.assertIn("## 明日执行结论", report)
        self.assertIn("| 明日执行对象 | 豫能控股(001896) |", report)
        self.assertIn("## 50%执行条件", report)
        self.assertIn("## 推导审计层", report)
        self.assertLess(report.index("## 明日执行结论"), report.index("## 明日账户建议"))
        self.assertNotIn("| 观察对象 | 豫能控股(001896)：观察对象，不是执行对象 |", report)
        self.assertEqual(data["two_layer_decision_payload"]["front_decision"]["execution_object"]["code"], "001896")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_renders_two_layer_front_decision_before_old_account_advice
```

Expected: failure because the new front decision layer is not wired into `runtime.py`.

- [ ] **Step 3: Wire payload and renderers into runtime**

Modify the imports near other report imports in `scripts/report/runtime.py`:

```python
from report.two_layer_decision_payload import (
    build_two_layer_decision_payload,
    render_derivation_audit_layer,
    render_front_decision_layer,
)
```

Add helper functions near `_store_runtime_sniper_target_derivation`:

```python
def _store_runtime_two_layer_decision_payload(payload, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(payload, dict) or not payload:
        return {}
    stored = dict(payload)
    for target in (data, execution_stage_context, market_research_snapshot):
        if isinstance(target, dict):
            target["two_layer_decision_payload"] = stored
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    return stored
```

After `final_target_resolution` and `position_decision` are available in runtime, build and store:

```python
two_layer_payload = build_two_layer_decision_payload(
    target_date=target_date,
    final_target_resolution=final_target_resolution,
    position_decision=position_decision,
    execution_stage_context=execution_stage_context,
)
_store_runtime_two_layer_decision_payload(
    two_layer_payload,
    data=data,
    execution_stage_context=execution_stage_context,
    market_research_snapshot=market_research_snapshot,
)
front_decision_lines = render_front_decision_layer(two_layer_payload)
```

Insert `front_decision_lines` before `明日账户建议` lines are appended. The exact local variable names may already exist near the front-page build. Preserve existing output after the new section.

Append the audit layer before the existing detailed appendix:

```python
report.extend(render_derivation_audit_layer(two_layer_payload))
```

Place this once after execution stages are complete and before detailed appendix/tail sections, so the audit layer appears after core market sections but before long process tables.

- [ ] **Step 4: Run the focused runtime test**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_renders_two_layer_front_decision_before_old_account_advice
```

Expected: pass.

- [ ] **Step 5: Run focused payload and runtime tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_report_runtime
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add scripts/report/runtime.py tests/test_report_runtime.py
git commit -m "feat(report): render two-layer daily decision"
```

## Task 3: Acceptance Audit

**Files:**
- Modify: `scripts/report/report_acceptance_audit.py`
- Modify: `tests/test_report_acceptance_audit.py`

- [ ] **Step 1: Add failing audit tests**

Add these tests to `tests/test_report_acceptance_audit.py`:

```python
    def test_audit_flags_b_level_without_conditions(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日仓位 | 条件满足才50%条件执行；不满足回到0% |\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 执行性质 | 50%条件执行，约50%仓位 |\n"
            "| 不满足条件 | 不参与 |\n\n"
            "## 明日账户建议\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日动作 | 条件满足才50%条件执行 |\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("b_level_conditions_missing", {finding["code"] for finding in result["findings"]})

    def test_audit_flags_execution_object_mismatch_between_front_and_audit_layer(self):
        markdown = (
            "# 2026-06-04 a股市场分析\n\n"
            "## 明日执行结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日执行对象 | 豫能控股(001896) |\n\n"
            "## 50%执行条件\n"
            "| 触发类型 | 必须满足 | 窗口 | 动作 |\n"
            "|----------|----------|------|------|\n"
            "| 低开承接型 | 靠近MA5；收回VWAP/0轴 | 09:50-10:10 | 50%条件执行 |\n"
            "| 主动进攻型 | 大单净流入达标；VWAP上方保持 | 09:30-09:35 | 50%条件执行 |\n\n"
            "## 推导审计层\n"
            "### Step 2：主方向与候选收缩\n"
            "#### 传给下一步\n"
            "- 条件执行对象：上海石化(600688)\n"
        )

        result = audit_report_markdown(markdown)

        self.assertIn("two_layer_execution_object_mismatch", {finding["code"] for finding in result["findings"]})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit
```

Expected: failure because the new audit checks do not exist.

- [ ] **Step 3: Add extraction helpers and checks**

In `scripts/report/report_acceptance_audit.py`, add helpers near target extraction functions:

```python
def _extract_front_execution_object(lines):
    front = _front_page_lines(lines)
    for line in front:
        text = str(line or "")
        if text.startswith("| 明日执行对象 |"):
            parts = [part.strip() for part in text.strip("|").split("|")]
            if len(parts) >= 2:
                return parts[1]
    return ""


def _extract_audit_layer_execution_object(lines):
    found = False
    for line in lines:
        text = str(line or "")
        if text.startswith("## 推导审计层"):
            found = True
            continue
        if not found:
            continue
        if "条件执行对象：" in text:
            return text.split("条件执行对象：", 1)[-1].strip()
    return ""


def _audit_two_layer_execution_object_consistency(lines):
    front_object = _extract_front_execution_object(lines)
    if not front_object:
        return []
    audit_object = _extract_audit_layer_execution_object(lines)
    if not audit_object:
        return []
    front_identity = _target_identity(front_object)
    audit_identity = _target_identity(audit_object)
    if front_identity and audit_identity and front_identity != audit_identity:
        return [
            _finding(
                "two_layer_execution_object_mismatch",
                f"front execution object {front_object} conflicts with audit-layer object {audit_object}",
            )
        ]
    return []


def _audit_b_level_conditions(lines):
    text = "\n".join(str(line or "") for line in lines)
    if "50%条件执行" not in text:
        return []
    if "## 50%执行条件" in text and "低开承接型" in text and "主动进攻型" in text:
        return []
    return [
        _finding(
            "b_level_conditions_missing",
            "report mentions 50%条件执行 but does not render both 50% trigger conditions",
        )
    ]
```

Add both checks to the main audit aggregation function where other `_audit_*` functions are collected:

```python
findings.extend(_audit_two_layer_execution_object_consistency(lines))
findings.extend(_audit_b_level_conditions(lines))
```

- [ ] **Step 4: Run audit tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "test(report): audit two-layer execution contract"
```

## Task 4: Replay Validation And Wording Sweep

**Files:**
- No planned source files unless replay reveals a focused bug.
- May update tests only if exact output assertions need the new wording.

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload tests.test_report_runtime tests.test_report_acceptance_audit tests.test_front_page_v2_renderer tests.test_candidate_quality_renderer tests.test_candidate_selection_stage tests.test_risk_review_stage tests.test_entry_plan_stage
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax and diff hygiene checks**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/two_layer_decision_payload.py scripts/report/runtime.py scripts/report/report_acceptance_audit.py
git diff --check -- scripts/report/two_layer_decision_payload.py scripts/report/runtime.py scripts/report/report_acceptance_audit.py tests/test_two_layer_decision_payload.py tests/test_report_runtime.py tests/test_report_acceptance_audit.py
```

Expected: both commands exit 0.

- [ ] **Step 3: Regenerate the 2026-06-04 replay report**

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
```

Expected:

- `reports/replay/2026-06-04_A股日报_完整版_replay.md` is saved.
- Output includes `日报一致性检查通过`.

- [ ] **Step 4: Inspect required report strings**

Run:

```bash
rg -n "明日执行结论|明日执行对象|50%执行条件|低开承接型|主动进攻型|推导审计层|传给下一步|观察对象" reports/replay/2026-06-04_A股日报_完整版_replay.md
```

Expected:

- `明日执行结论` appears before `明日账户建议`.
- `明日执行对象` appears with the selected stock.
- `50%执行条件` includes both `低开承接型` and `主动进攻型`.
- `推导审计层` includes Step 2-5 and `传给下一步`.
- `观察对象` should not appear in the new front decision layer. If it appears only in older appendix compatibility sections, record that as follow-up unless it conflicts with the front decision.

- [ ] **Step 5: Run acceptance audit on replay**

Run:

```bash
.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/replay/2026-06-04_A股日报_完整版_replay.md
```

Expected: exit 0.

- [ ] **Step 6: Final commit**

If Task 4 required source or test fixes, commit them:

```bash
git add <changed-files>
git commit -m "fix(report): satisfy two-layer replay validation"
```

If no files changed, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - Front decision layer: Task 1 and Task 2.
  - `明日执行对象` / `条件执行对象`: Task 1 and Task 3.
  - 50% low-open and active-attack conditions: Task 1 and Task 4.
  - Money threshold size bucket: Task 1.
  - Step audit template and pass-forward fields: Task 1 and Task 2.
  - Acceptance checks: Task 3 and Task 4.
  - Replay validation: Task 4.

- Placeholder scan:
  - No `TBD`, `TODO`, or vague "add tests" steps.
  - Every task has exact files, commands, and expected results.

- Scope control:
  - The plan adds a compatibility payload and renderers.
  - The plan does not rebuild data collectors or the whole trading judgment engine.
