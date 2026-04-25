# Daily Report Reasoning Mode Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the no-API `2.5` reasoning-decision layer so current-conversation or cached reasoning can feed the daily report through structured JSON, validation, rendering, and audit.

**Architecture:** Deterministic report code builds a small reasoning input packet, validates a structured `reasoning_decision.v1` object, optionally stores it as a replayable artifact, and renders only the decision surface into the front page. The model never writes the report body directly; current implementation supports manual/current-conversation or deterministic decision artifacts, leaving API-backed reasoning behind the same schema for a later phase.

**Tech Stack:** Python standard library, existing `scripts/report` modules, `unittest`, Markdown skill references, replay audit.

---

## File Structure

- Modify: `SKILL.md`
  - Add `references/reasoning-mode-contract.md` to the router for report generation, review, defect fixing, and skill optimization.
- Modify: `references/report-contract.md`
  - State that future report changes inherit both report contract and reasoning contract.
- Create: `references/reasoning-mode-contract.md`
  - Human-facing contract for no-API reasoning mode, input/decision boundaries, and no chain-of-thought output.
- Modify: `tests/test_daily_report_skill_docs.py`
  - Protect the skill routing and inherited reasoning contract.
- Create: `scripts/report/reasoning_decision_support.py`
  - Build stable input packets, compute input hashes, validate decision JSON, and derive effective unique target from a decision.
- Create: `tests/test_reasoning_decision_support.py`
  - Unit tests for packet building, hashing, validation, and target derivation.
- Create: `scripts/report/reasoning_decision_cache.py`
  - Save and load replayable manual/current-conversation decision artifacts.
- Create: `tests/test_reasoning_decision_cache.py`
  - Unit tests for stable cache keys and cache round trips.
- Create: `scripts/report/reasoning_decision_renderer.py`
  - Render a compact front-page decision surface from validated decision JSON.
- Modify: `scripts/report/front_page_v2_renderer.py`
  - Insert the decision surface into the execution-plan section and let validated decisions drive the unique target when present.
- Modify: `tests/test_front_page_v2_renderer.py`
  - Verify reasoning decisions render as conclusion/evidence/trigger/failure/exclusion, not chain-of-thought.
- Modify: `scripts/report/report_acceptance_audit.py`
  - Audit reasoning-decision surfaces for required labels and chain-of-thought leakage.
- Modify: `tests/test_report_acceptance_audit.py`
  - Verify audit catches incomplete reasoning surfaces and leaked reasoning-chain labels.

---

### Task 1: Add Reasoning Contract Documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `references/report-contract.md`
- Create: `references/reasoning-mode-contract.md`
- Modify: `tests/test_daily_report_skill_docs.py`

- [ ] **Step 1: Write the failing docs test**

Add this test method to `tests/test_daily_report_skill_docs.py` inside `DailyReportSkillDocsTest`:

```python
    def test_skill_and_report_contract_inherit_reasoning_mode_contract(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        reasoning_contract = self._read("references/reasoning-mode-contract.md")
        combined = "\n".join([skill, report_contract, reasoning_contract])

        for required in [
            "references/reasoning-mode-contract.md",
            "reasoning decision JSON",
            "no-API first",
            "current-conversation reasoning",
            "do not expose chain-of-thought",
            "deterministic facts",
            "bounded decisions",
            "future report changes inherit both report contract and reasoning contract",
        ]:
            self.assertIn(required, combined)
```

- [ ] **Step 2: Run the docs test and verify it fails**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs
```

Expected: FAIL because `references/reasoning-mode-contract.md` does not exist or is not routed yet.

- [ ] **Step 3: Add the reasoning-mode reference**

Create `references/reasoning-mode-contract.md` with this content:

```markdown
# Reasoning Mode Contract

This reference is for bounded daily-report reasoning. It is not a prompt manual and not an API integration guide.

## Core Contract

- Use no-API first: current-conversation reasoning or deterministic artifacts may produce a reasoning decision JSON.
- Code owns deterministic facts: market snapshots, candidate pools, turnover share, source status, and replay artifacts.
- Reasoning mode owns bounded decisions: action, mainline state, unique target judgment, trigger conditions, failure conditions, and exclusion reasons.
- The report renderer owns expression: it shows only conclusion, evidence, triggers, failures, exclusions, and confidence.
- Do not expose chain-of-thought, hidden reasoning traces, or long draft reasoning in the daily report.

## Decision Boundary

The only object allowed to cross from reasoning into report rendering is `reasoning_decision.v1`.

Required fields:

- `schema_version`
- `target_date`
- `input_hash`
- `prompt_version`
- `model_source`
- `action`
- `mainline_state`
- `unique_target`
- `conclusion`
- `evidence`
- `trigger_conditions`
- `failure_conditions`
- `excluded_candidates`
- `confidence`

## Safety Rules

- Evidence must point to fields from the reasoning input packet.
- A unique target must come from the candidate pool.
- `conditional_entry` must include trigger and failure conditions.
- Low confidence cannot create an aggressive action.
- Missing or degraded data must not become fake certainty.
- API-backed reasoning may be added later, but it must fill the same JSON and pass the same validator before rendering.
```

- [ ] **Step 4: Route the reasoning contract from the skill**

In `SKILL.md`, update the intent routes so report generation, report review, defect fixing, and skill optimization mention `references/reasoning-mode-contract.md`.

Use this operating rule under `## Operating Rules`:

```markdown
- Treat reasoning as bounded decision support: future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
```

Update `## References` with:

```markdown
- `references/reasoning-mode-contract.md` - no-API first reasoning decision JSON, boundaries, and no chain-of-thought output.
```

- [ ] **Step 5: Update report contract inheritance**

In `references/report-contract.md`, extend `## Future Change Inheritance` with:

```markdown
- Future report changes inherit both report contract and reasoning contract unless the latest user instruction explicitly overrides them.
```

- [ ] **Step 6: Run the docs test and verify it passes**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs
```

Expected: OK.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add SKILL.md references/report-contract.md references/reasoning-mode-contract.md tests/test_daily_report_skill_docs.py
git commit -m "document reasoning mode contract"
```

---

### Task 2: Build Stable Reasoning Input Packets

**Files:**
- Create: `scripts/report/reasoning_decision_support.py`
- Create: `tests/test_reasoning_decision_support.py`

- [ ] **Step 1: Write failing packet tests**

Create `tests/test_reasoning_decision_support.py` with:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.reasoning_decision_support import build_reasoning_input_packet, compute_input_hash


class ReasoningDecisionSupportTest(unittest.TestCase):
    def test_builds_stable_reasoning_input_packet_from_snapshot(self):
        snapshot = {
            "market_fit_calibration": {"fit_label": "主线有效，池子偏窄"},
            "mainline_turnover_summary": {
                "current_mainline": "半导体",
                "double_mainline_summary": {
                    "cycle_mainline": "半导体",
                    "daily_attack_line": "半导体",
                    "relationship": "周期主线与当天主攻线一致",
                    "tomorrow_action": "继续围绕半导体观察承接",
                },
            },
            "current_sector_turnover_snapshot": {
                "date": "2026-04-24",
                "sector_name": "半导体",
                "turnover_share_pct": 18.1,
            },
            "recent_sector_turnover_history": [
                {"date": "2026-04-23", "sector_name": "半导体", "turnover_share_pct": 15.8}
            ],
            "candidate_pool": [
                {
                    "code": "300613",
                    "name": "富瀚微",
                    "sector": "半导体",
                    "qualification": "观察，等10点确认",
                    "evidence": {"承接": "明日验证承接", "资金痕迹": "主线资金主动进攻"},
                }
            ],
            "source_status": {"ths_sector": "ok"},
        }

        packet = build_reasoning_input_packet("2026-04-24", snapshot, final_gate={"final_action": "观察"})

        self.assertEqual(packet["schema_version"], "reasoning_input.v1")
        self.assertEqual(packet["target_date"], "2026-04-24")
        self.assertEqual(packet["mainline_snapshot"]["current_mainline"], "半导体")
        self.assertEqual(packet["candidate_pool"][0]["id"], "300613")
        self.assertEqual(packet["candidate_pool"][0]["name"], "富瀚微")
        self.assertEqual(packet["execution_contract"]["final_action"], "观察")
        self.assertEqual(packet["source_status"]["ths_sector"], "ok")

    def test_compute_input_hash_is_order_stable_for_dict_keys(self):
        left = {"b": 2, "a": {"d": 4, "c": 3}}
        right = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(compute_input_hash(left), compute_input_hash(right))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the packet tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_support
```

Expected: FAIL with `ModuleNotFoundError` for `report.reasoning_decision_support`.

- [ ] **Step 3: Implement packet building and hashing**

Create `scripts/report/reasoning_decision_support.py` with:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping


INPUT_SCHEMA_VERSION = "reasoning_input.v1"
DECISION_SCHEMA_VERSION = "reasoning_decision.v1"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_input_hash(packet: Mapping[str, Any]) -> str:
    return hashlib.sha256(_stable_json(packet).encode("utf-8")).hexdigest()


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _normalize_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    code = str(candidate.get("code") or candidate.get("id") or "").strip()
    name = str(candidate.get("name") or "").strip()
    return {
        "id": code or name,
        "code": code,
        "name": name,
        "sector": candidate.get("sector") or candidate.get("sector_name") or "",
        "qualification": candidate.get("qualification") or candidate.get("tomorrow_qualification") or candidate.get("action_rule") or "",
        "evidence": _as_dict(candidate.get("evidence")),
    }


def _candidate_pool(snapshot: Mapping[str, Any]) -> List[Dict[str, Any]]:
    raw_candidates = _as_list(snapshot.get("candidate_pool"))
    if not raw_candidates:
        raw_candidates = _as_list(snapshot.get("core_candidates"))
    return [_normalize_candidate(item) for item in raw_candidates if isinstance(item, Mapping)]


def build_reasoning_input_packet(target_date: str, market_research_snapshot: Mapping[str, Any] | None, final_gate: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    snapshot = _as_dict(market_research_snapshot)
    mainline_summary = _as_dict(snapshot.get("mainline_turnover_summary"))
    packet = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "target_date": str(target_date or ""),
        "market_base": {
            "market_fit_calibration": _as_dict(snapshot.get("market_fit_calibration")),
            "state_machine": _as_dict(snapshot.get("state_machine")),
        },
        "mainline_snapshot": {
            "current_mainline": mainline_summary.get("current_mainline") or "",
            "double_mainline_summary": _as_dict(mainline_summary.get("double_mainline_summary")),
            "current_sector_turnover_snapshot": _as_dict(snapshot.get("current_sector_turnover_snapshot")),
        },
        "turnover_share_history": _as_list(snapshot.get("recent_sector_turnover_history")),
        "candidate_pool": _candidate_pool(snapshot),
        "execution_contract": _as_dict(final_gate),
        "risk_context": _as_dict(snapshot.get("risk_context")),
        "source_status": _as_dict(snapshot.get("source_status")),
    }
    packet["input_hash"] = compute_input_hash({key: value for key, value in packet.items() if key != "input_hash"})
    return packet
```

- [ ] **Step 4: Run the packet tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_support
```

Expected: OK.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/report/reasoning_decision_support.py tests/test_reasoning_decision_support.py
git commit -m "add reasoning input packet support"
```

---

### Task 3: Validate Reasoning Decision JSON

**Files:**
- Modify: `scripts/report/reasoning_decision_support.py`
- Modify: `tests/test_reasoning_decision_support.py`

- [ ] **Step 1: Write failing validation tests**

Add these imports and tests to `tests/test_reasoning_decision_support.py`:

```python
from report.reasoning_decision_support import validate_reasoning_decision
```

```python
    def _packet(self):
        return build_reasoning_input_packet(
            "2026-04-24",
            {
                "mainline_turnover_summary": {"current_mainline": "半导体"},
                "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
            },
            final_gate={"final_action": "观察"},
        )

    def _valid_decision(self, packet):
        return {
            "schema_version": "reasoning_decision.v1",
            "target_date": packet["target_date"],
            "input_hash": packet["input_hash"],
            "prompt_version": "manual-current-conversation-v1",
            "model_source": "manual",
            "action": "observe",
            "mainline_state": "strengthening",
            "unique_target": None,
            "conclusion": "主线仍需确认，只观察承接。",
            "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
            "trigger_conditions": ["10点后主线继续放量"],
            "failure_conditions": ["主线回落"],
            "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "60分钟确认未完成"}],
            "confidence": "medium",
        }

    def test_validates_well_formed_reasoning_decision(self):
        packet = self._packet()
        result = validate_reasoning_decision(packet, self._valid_decision(packet))

        self.assertTrue(result["passed"], result["findings"])

    def test_rejects_unique_target_outside_candidate_pool(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["unique_target"] = "999999"

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("unique_target_not_in_candidate_pool", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_unknown_evidence_field(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["evidence"] = [{"field": "unknown.path", "summary": "不可验证证据"}]

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("evidence_field_unknown", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_conditional_entry_without_trigger_and_failure(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["action"] = "conditional_entry"
        decision["unique_target"] = "300613"
        decision["trigger_conditions"] = []

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("conditional_entry_missing_conditions", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_rejects_low_confidence_aggressive_action(self):
        packet = self._packet()
        decision = self._valid_decision(packet)
        decision["action"] = "conditional_entry"
        decision["unique_target"] = "300613"
        decision["confidence"] = "low"

        result = validate_reasoning_decision(packet, decision)

        self.assertIn("low_confidence_aggressive_action", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])
```

- [ ] **Step 2: Run validation tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_support
```

Expected: FAIL because `validate_reasoning_decision` is not defined.

- [ ] **Step 3: Implement validation**

Append this implementation to `scripts/report/reasoning_decision_support.py`:

```python
ALLOWED_ACTIONS = {"do_nothing", "observe", "conditional_entry"}
ALLOWED_MAINLINE_STATES = {"strengthening", "diverging", "fading", "unclear"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_MODEL_SOURCES = {"manual", "deterministic_fallback", "api"}


def _finding(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _flatten_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            paths.update(_flatten_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            paths.add(path)
            paths.update(_flatten_paths(item, path))
    return paths


def _candidate_ids(packet: Mapping[str, Any]) -> set[str]:
    ids = set()
    for item in _as_list(packet.get("candidate_pool")):
        if not isinstance(item, Mapping):
            continue
        for key in ("id", "code"):
            value = str(item.get(key) or "").strip()
            if value:
                ids.add(value)
    return ids


def validate_reasoning_decision(packet: Mapping[str, Any], decision: Mapping[str, Any]) -> Dict[str, Any]:
    packet = _as_dict(packet)
    decision = _as_dict(decision)
    findings: List[Dict[str, str]] = []

    if decision.get("schema_version") != DECISION_SCHEMA_VERSION:
        findings.append(_finding("unsupported_schema_version", "reasoning decision schema_version must be reasoning_decision.v1"))
    if decision.get("target_date") != packet.get("target_date"):
        findings.append(_finding("target_date_mismatch", "reasoning decision target_date must match input packet"))
    if decision.get("input_hash") != packet.get("input_hash"):
        findings.append(_finding("input_hash_mismatch", "reasoning decision input_hash must match input packet"))
    if decision.get("action") not in ALLOWED_ACTIONS:
        findings.append(_finding("invalid_action", "reasoning decision action is not supported"))
    if decision.get("mainline_state") not in ALLOWED_MAINLINE_STATES:
        findings.append(_finding("invalid_mainline_state", "reasoning decision mainline_state is not supported"))
    if decision.get("confidence") not in ALLOWED_CONFIDENCE:
        findings.append(_finding("invalid_confidence", "reasoning decision confidence is not supported"))
    if decision.get("model_source") not in ALLOWED_MODEL_SOURCES:
        findings.append(_finding("invalid_model_source", "reasoning decision model_source is not supported"))

    candidate_ids = _candidate_ids(packet)
    unique_target = decision.get("unique_target")
    if decision.get("action") == "do_nothing" and unique_target:
        findings.append(_finding("do_nothing_has_unique_target", "do_nothing decisions must not name a unique target"))
    if unique_target and str(unique_target) not in candidate_ids:
        findings.append(_finding("unique_target_not_in_candidate_pool", "unique target must come from the candidate pool"))

    if decision.get("action") == "conditional_entry" and (not decision.get("trigger_conditions") or not decision.get("failure_conditions")):
        findings.append(_finding("conditional_entry_missing_conditions", "conditional entry must include trigger and failure conditions"))
    if decision.get("confidence") == "low" and decision.get("action") == "conditional_entry":
        findings.append(_finding("low_confidence_aggressive_action", "low confidence cannot create conditional entry"))

    known_paths = _flatten_paths(packet)
    for item in _as_list(decision.get("evidence")):
        if not isinstance(item, Mapping):
            findings.append(_finding("evidence_item_invalid", "evidence items must be objects"))
            continue
        field = str(item.get("field") or "").strip()
        if field not in known_paths:
            findings.append(_finding("evidence_field_unknown", f"evidence field is not present in input packet: {field}"))

    for item in _as_list(decision.get("excluded_candidates")):
        if not isinstance(item, Mapping):
            findings.append(_finding("excluded_candidate_invalid", "excluded candidates must be objects"))
            continue
        candidate_id = str(item.get("id") or item.get("code") or "").strip()
        if candidate_id and candidate_id not in candidate_ids:
            findings.append(_finding("excluded_candidate_unknown", f"excluded candidate is not present in input packet: {candidate_id}"))

    return {"passed": not findings, "findings": findings}
```

- [ ] **Step 4: Run validation tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_support
```

Expected: OK.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/report/reasoning_decision_support.py tests/test_reasoning_decision_support.py
git commit -m "validate reasoning decisions"
```

---

### Task 4: Add Replayable Manual Decision Cache

**Files:**
- Create: `scripts/report/reasoning_decision_cache.py`
- Create: `tests/test_reasoning_decision_cache.py`

- [ ] **Step 1: Write failing cache tests**

Create `tests/test_reasoning_decision_cache.py` with:

```python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.reasoning_decision_cache import (
    load_reasoning_decision_cache,
    reasoning_cache_key,
    save_reasoning_decision_cache,
)


class ReasoningDecisionCacheTest(unittest.TestCase):
    def test_cache_key_is_stable_and_filename_safe(self):
        key = reasoning_cache_key(
            target_date="2026-04-24",
            input_hash="abcdef1234567890",
            schema_version="reasoning_decision.v1",
            prompt_version="manual-current-conversation-v1",
            model_source="manual",
        )

        self.assertEqual(key, "2026-04-24_abcdef123456_reasoning_decision.v1_manual-current-conversation-v1_manual")

    def test_saves_and_loads_reasoning_decision_cache_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            decision = {
                "schema_version": "reasoning_decision.v1",
                "target_date": "2026-04-24",
                "input_hash": "abcdef1234567890",
                "prompt_version": "manual-current-conversation-v1",
                "model_source": "manual",
                "action": "observe",
                "mainline_state": "unclear",
                "unique_target": None,
                "conclusion": "先观察。",
                "evidence": [],
                "trigger_conditions": ["10点确认"],
                "failure_conditions": ["主线回落"],
                "excluded_candidates": [],
                "confidence": "medium",
            }

            saved_path = save_reasoning_decision_cache(cache_dir, decision)
            loaded = load_reasoning_decision_cache(cache_dir, decision)

            self.assertEqual(saved_path.name, "2026-04-24_abcdef123456_reasoning_decision.v1_manual-current-conversation-v1_manual.json")
            self.assertEqual(loaded["decision"]["conclusion"], "先观察。")
            self.assertEqual(loaded["target_date"], "2026-04-24")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run cache tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_cache
```

Expected: FAIL with `ModuleNotFoundError` for `report.reasoning_decision_cache`.

- [ ] **Step 3: Implement cache module**

Create `scripts/report/reasoning_decision_cache.py` with:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping


def _safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_", ".") else "-" for char in str(value or ""))


def reasoning_cache_key(*, target_date: str, input_hash: str, schema_version: str, prompt_version: str, model_source: str) -> str:
    return "_".join(
        [
            _safe(target_date),
            _safe(str(input_hash)[:12]),
            _safe(schema_version),
            _safe(prompt_version),
            _safe(model_source),
        ]
    )


def _key_from_decision(decision: Mapping[str, Any]) -> str:
    return reasoning_cache_key(
        target_date=str(decision.get("target_date") or ""),
        input_hash=str(decision.get("input_hash") or ""),
        schema_version=str(decision.get("schema_version") or ""),
        prompt_version=str(decision.get("prompt_version") or ""),
        model_source=str(decision.get("model_source") or ""),
    )


def save_reasoning_decision_cache(cache_dir: Path | str, decision: Mapping[str, Any]) -> Path:
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target_date": decision.get("target_date"),
        "input_hash": decision.get("input_hash"),
        "schema_version": decision.get("schema_version"),
        "prompt_version": decision.get("prompt_version"),
        "model_source": decision.get("model_source"),
        "decision": dict(decision),
    }
    path = cache_path / f"{_key_from_decision(decision)}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_reasoning_decision_cache(cache_dir: Path | str, decision_or_key: Mapping[str, Any] | str) -> Dict[str, Any]:
    cache_path = Path(cache_dir)
    key = _key_from_decision(decision_or_key) if isinstance(decision_or_key, Mapping) else str(decision_or_key)
    path = cache_path / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run cache tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_reasoning_decision_cache
```

Expected: OK.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add scripts/report/reasoning_decision_cache.py tests/test_reasoning_decision_cache.py
git commit -m "add reasoning decision cache"
```

---

### Task 5: Render Reasoning Decision Surface On The Front Page

**Files:**
- Create: `scripts/report/reasoning_decision_renderer.py`
- Modify: `scripts/report/reasoning_decision_support.py`
- Modify: `scripts/report/front_page_v2_renderer.py`
- Modify: `tests/test_front_page_v2_renderer.py`

- [ ] **Step 1: Write failing renderer tests**

Add this test to `tests/test_front_page_v2_renderer.py`:

```python
    def test_front_page_renders_reasoning_decision_without_chain_of_thought(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "observe",
                        "mainline_state": "strengthening",
                        "unique_target": None,
                        "conclusion": "主线仍需确认，明天只观察承接。",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "候选股完成60分钟确认"],
                        "failure_conditions": ["主线回落", "候选股承接失败"],
                        "excluded_candidates": [{"id": "300613", "name": "富瀚微", "reason": "60分钟确认未完成"}],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("### 0. 推理裁决", rendered)
        self.assertIn("| 裁决 | observe |", rendered)
        self.assertIn("| 结论 | 主线仍需确认，明天只观察承接。 |", rendered)
        self.assertIn("| 关键证据 | 主线为半导体 |", rendered)
        self.assertIn("| 触发条件 | 10点后主线继续放量；候选股完成60分钟确认 |", rendered)
        self.assertIn("| 失败条件 | 主线回落；候选股承接失败 |", rendered)
        self.assertIn("| 排除对象 | 富瀚微(300613)：60分钟确认未完成 |", rendered)
        self.assertIn("| 置信度 | medium |", rendered)
        self.assertNotIn("chain-of-thought", rendered)
        self.assertNotIn("思维链", rendered)
```

Add this second test to verify the decision can drive the unique target:

```python
    def test_reasoning_decision_unique_target_drives_unique_action_when_snapshot_target_is_missing(self):
        rendered = "\n".join(
            render_front_page_v2(
                [],
                target_date="2026-04-24",
                market_research_snapshot={
                    "candidate_pool": [{"code": "300613", "name": "富瀚微", "sector": "半导体"}],
                    "mainline_turnover_summary": {"current_mainline": "半导体"},
                    "reasoning_decision": {
                        "action": "conditional_entry",
                        "mainline_state": "strengthening",
                        "unique_target": "300613",
                        "conclusion": "只看富瀚微，满足确认才允许条件试错。",
                        "evidence": [{"field": "mainline_snapshot.current_mainline", "summary": "主线为半导体"}],
                        "trigger_conditions": ["10点后主线继续放量", "富瀚微完成60分钟确认"],
                        "failure_conditions": ["主线回落"],
                        "excluded_candidates": [],
                        "confidence": "medium",
                    },
                },
            )
        )

        self.assertIn("| 只看唯一对象 | 富瀚微(300613) | 主线确认 + 承接 + 60分钟确认 | 不做 |", rendered)
        self.assertIn("| 防守观察 | 不主动 | 半导体 | 半导体 | 先看市场基底 | 富瀚微(300613) |", rendered)
```

- [ ] **Step 2: Run renderer tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_front_page_v2_renderer
```

Expected: FAIL because no reasoning-decision surface is rendered.

- [ ] **Step 3: Add rendering helpers**

Create `scripts/report/reasoning_decision_renderer.py` with:

```python
from __future__ import annotations

from typing import Any, Mapping


def _join(items: Any) -> str:
    if not isinstance(items, list):
        return "-"
    values = [str(item).strip() for item in items if str(item).strip()]
    return "；".join(values) if values else "-"


def _evidence_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("evidence")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        summary = str(item.get("summary") or "").strip()
        if summary:
            values.append(summary)
    return "；".join(values) if values else "-"


def _excluded_text(decision: Mapping[str, Any]) -> str:
    items = decision.get("excluded_candidates")
    if not isinstance(items, list):
        return "-"
    values = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        code = str(item.get("id") or item.get("code") or "").strip()
        reason = str(item.get("reason") or "").strip()
        label = f"{name}({code})" if name and code else name or code or "-"
        values.append(f"{label}：{reason or '-'}")
    return "；".join(values) if values else "-"


def render_reasoning_decision_lines(decision: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(decision, Mapping) or not decision:
        return []
    return [
        "### 0. 推理裁决",
        "| 项目 | 内容 |",
        "|------|------|",
        f"| 裁决 | {decision.get('action') or '-'} |",
        f"| 主线状态 | {decision.get('mainline_state') or '-'} |",
        f"| 结论 | {decision.get('conclusion') or '-'} |",
        f"| 关键证据 | {_evidence_text(decision)} |",
        f"| 触发条件 | {_join(decision.get('trigger_conditions'))} |",
        f"| 失败条件 | {_join(decision.get('failure_conditions'))} |",
        f"| 排除对象 | {_excluded_text(decision)} |",
        f"| 置信度 | {decision.get('confidence') or '-'} |",
        "",
    ]
```

- [ ] **Step 4: Add unique-target derivation helper**

Append this to `scripts/report/reasoning_decision_support.py`:

```python
def derive_unique_action_target_from_reasoning_decision(snapshot: Mapping[str, Any]) -> Dict[str, str]:
    snapshot = _as_dict(snapshot)
    decision = _as_dict(snapshot.get("reasoning_decision"))
    target_id = str(decision.get("unique_target") or "").strip()
    if not target_id:
        return {}
    for candidate in _candidate_pool(snapshot):
        if target_id in {str(candidate.get("id") or ""), str(candidate.get("code") or "")}:
            return {
                "name": str(candidate.get("name") or "唯一对象"),
                "code": str(candidate.get("code") or candidate.get("id") or target_id),
                "condition": "主线确认 + 承接 + 60分钟确认",
            }
    return {}
```

- [ ] **Step 5: Wire renderer into `front_page_v2_renderer.py`**

At the top of `scripts/report/front_page_v2_renderer.py`, add:

```python
from report.reasoning_decision_renderer import render_reasoning_decision_lines
from report.reasoning_decision_support import derive_unique_action_target_from_reasoning_decision
```

Change `_has_unique_action_target` to:

```python
def _effective_unique_action_target(snapshot):
    snapshot = snapshot or {}
    target = snapshot.get("unique_action_target") or {}
    if isinstance(target, dict) and (target.get("name") or target.get("code")):
        return target
    return derive_unique_action_target_from_reasoning_decision(snapshot)


def _has_unique_action_target(snapshot):
    target = _effective_unique_action_target(snapshot)
    return isinstance(target, dict) and bool(target.get("name") or target.get("code"))
```

Change `_unique_action_target_lines` so its first line is:

```python
    target = _effective_unique_action_target(snapshot)
```

Change `_final_summary_lines` so the target line is:

```python
    target = _effective_unique_action_target(snapshot)
```

Change `_execution_plan_lines` to:

```python
def _execution_plan_lines(snapshot=None):
    decision_lines = render_reasoning_decision_lines((snapshot or {}).get("reasoning_decision"))
    return [
        "## 六、明日执行计划",
        *decision_lines,
        *_unique_action_target_lines(snapshot),
        "| 时间窗口 | 要看什么 | 买入权限 | 卖出/风控 | 结论 |",
        "|----------|----------|----------|-----------|------|",
        "| 09:25-09:40 | 竞价强弱、主线核心是否被核、跌停扩散 | 默认无 | 有旧仓先看是否需要降风险 | 不抢 |",
        "| 09:50-10:10 | 市场底色、主线承接、唯一对象强弱 | 仅主线核心可进入观察买点 | 10:00左右处理弱仓/错仓 | 核心确认窗口 |",
        "| 10:00左右卖 | 弱仓、错仓、破结构仓位 | 无 | 该卖就卖，不做自救 | 防大亏 |",
        "| 10:00左右买 | 只看周期主线核心，且必须有承接 | 满足60分钟确认才允许 | 买后用30分钟结构止损 | 小仓或不开 |",
        "| 午后 | 看主线是否延续，不追轮动末端 | 默认谨慎 | 若走弱继续降风险 | 不扩大试错 |",
        "| 尾盘 | 只判断是否量化电风扇行情 | 仅电风扇行情例外，次日高开兑现 | 非电风扇不尾盘开新仓 | 例外，不是常规 |",
        "",
    ]
```

- [ ] **Step 6: Run renderer tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_front_page_v2_renderer
```

Expected: OK.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add scripts/report/reasoning_decision_renderer.py scripts/report/reasoning_decision_support.py scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "render reasoning decision surface"
```

---

### Task 6: Extend Report Acceptance Audit For Reasoning Surfaces

**Files:**
- Modify: `scripts/report/report_acceptance_audit.py`
- Modify: `tests/test_report_acceptance_audit.py`

- [ ] **Step 1: Write failing audit tests**

Add these tests to `tests/test_report_acceptance_audit.py`:

```python
    def test_audit_flags_reasoning_surface_missing_required_rows(self):
        bad = GOOD_MARKDOWN.replace(
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
            "### 0. 推理裁决\n"
            "| 项目 | 内容 |\n"
            "|------|------|\n"
            "| 裁决 | observe |\n"
            "| 结论 | 主线仍需确认。 |\n\n"
            "| 明日唯一动作 | 标的 | 条件 | 不满足怎么办 |",
        )

        result = audit_report_markdown(bad)

        self.assertIn("reasoning_surface_incomplete", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_flags_reasoning_chain_leakage(self):
        bad = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            "### 0. 推理裁决\n"
            "思维链：先这样想，再那样想。\n\n"
            "## 七、最终结论",
        )

        result = audit_report_markdown(bad)

        self.assertIn("reasoning_chain_leakage", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])
```

- [ ] **Step 2: Run audit tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_report_acceptance_audit
```

Expected: FAIL because reasoning-surface audit is not implemented.

- [ ] **Step 3: Implement reasoning-surface audit**

In `scripts/report/report_acceptance_audit.py`, add constants near the other markers:

```python
REASONING_SURFACE_HEADING = "### 0. 推理裁决"
REASONING_REQUIRED_LABELS = ("裁决", "结论", "关键证据", "触发条件", "失败条件", "排除对象", "置信度")
REASONING_CHAIN_LEAK_MARKERS = ("chain-of-thought", "思维链", "完整推理链", "隐藏推理")
```

Add this function:

```python
def _audit_reasoning_surface(lines):
    findings = []
    text = "\n".join(_front_page_lines(lines))
    for marker in REASONING_CHAIN_LEAK_MARKERS:
        if marker in text:
            findings.append(
                _finding(
                    "reasoning_chain_leakage",
                    f"front page must not expose reasoning chain marker: {marker}",
                )
            )
    if REASONING_SURFACE_HEADING not in lines:
        return findings
    section = _section_after(lines, REASONING_SURFACE_HEADING)
    section_text = "\n".join(section)
    missing = [label for label in REASONING_REQUIRED_LABELS if f"| {label} |" not in section_text]
    if missing:
        findings.append(
            _finding(
                "reasoning_surface_incomplete",
                "reasoning surface is missing required rows: " + ", ".join(missing),
            )
        )
    return findings
```

Add this helper near `_section_between`:

```python
def _section_after(lines, start_marker):
    try:
        start = list(lines).index(start_marker)
    except ValueError:
        return []
    section = []
    for line in list(lines)[start + 1 :]:
        if str(line).startswith("## ") or str(line).startswith("### ") and line != start_marker:
            break
        section.append(line)
    return section
```

Add `_audit_reasoning_surface(lines)` to the list inside `audit_report_markdown`.

- [ ] **Step 4: Run audit tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_report_acceptance_audit
```

Expected: OK.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "audit reasoning decision surface"
```

---

### Task 7: Contract Regression And Replay Verification

**Files:**
- No new files expected.
- Verify: `SKILL.md`, `references/*.md`, `scripts/report/*.py`, `tests/*.py`

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs tests.test_reasoning_decision_support tests.test_reasoning_decision_cache tests.test_front_page_v2_renderer tests.test_report_acceptance_audit
```

Expected: OK.

- [ ] **Step 2: Run current replay generation**

Run:

```bash
venv/bin/python scripts/daily_report_entry_demo.py 2026-04-24 --replay
```

Expected: command exits 0 and updates `reports/replay/2026-04-24_A股日报_完整版_replay.md`.

- [ ] **Step 3: Run replay acceptance audit**

Run:

```bash
venv/bin/python scripts/report/report_acceptance_audit.py reports/replay/2026-04-24_A股日报_完整版_replay.md
```

Expected: `report_acceptance_audit: passed`.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output and exit 0.

- [ ] **Step 5: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intended source, test, reference, and replay artifacts appear. If replay output changes only because of timestamp or generated noise unrelated to reasoning mode, do not commit the replay artifact.

- [ ] **Step 6: Commit final verification-only updates if any**

If only source and tests are already committed and no intended files remain, skip this step. If a final intended docs or audit adjustment remains, run:

```bash
git add <intended-files>
git commit -m "verify reasoning mode contract integration"
```

---

## Self-Review

Spec coverage:

- `references/reasoning-mode-contract.md` and `SKILL.md` route the inherited reasoning contract.
- `reasoning_decision_support.py` covers input packet, hash, schema validation, and unique-target derivation.
- `reasoning_decision_cache.py` covers replayable manual/current-conversation artifacts.
- `reasoning_decision_renderer.py` and `front_page_v2_renderer.py` cover report consumption without chain-of-thought.
- `report_acceptance_audit.py` covers rendered output violations.
- Replay commands cover the final acceptance surface.

No API is added in this plan. API-backed reasoning remains behind the same schema for a later phase.

No hidden chain-of-thought is rendered; only conclusion, evidence, triggers, failures, exclusions, and confidence enter the report.
