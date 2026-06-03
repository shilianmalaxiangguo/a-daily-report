# Mainline Attack Evidence Structure Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mainline_attack_evidence_summary` so daily reports confirm mainlines from structured fund-attack evidence instead of free-form prose.

**Architecture:** Add focused helpers inside the existing mainline turnover runtime first, then thread the summary through the existing support resolver and capacity/regime summary. Keep old `mainline_capacity_regime_summary` and `double_mainline_summary` compatibility paths intact so historical reports do not break.

**Tech Stack:** Python stdlib, existing `unittest` suite, existing report runtime modules.

---

## File Structure

- Modify `scripts/domains/market_state/mainline_turnover_summary_runtime.py`
  - Add field normalization helpers.
  - Add `build_mainline_attack_evidence_summary`.
  - Use the attack summary when building `mainline_capacity_regime_summary`.
- Modify `scripts/report/mainline_turnover_summary_support.py`
  - Add `resolve_mainline_attack_evidence_summary(context)`.
  - Keep all existing resolver behavior unchanged.
- Modify `scripts/report/reasoning_decision_support.py`
  - Add `mainline_attack_evidence_summary` to the stable reasoning input packet.
- Tests:
  - `tests/test_mainline_attack_evidence_runtime.py`
  - `tests/test_mainline_turnover_summary_support.py`
  - `tests/test_mainline_turnover_summary_runtime.py`
  - `tests/test_reasoning_decision_support.py`

## Data Source Priority

The runtime accepts normalized inputs; upstream collectors can map raw data later.

| Evidence field | Preferred source | Fallback |
|---|---|---|
| `net_inflow_amount`, `net_inflow_rank` | industry capital-flow ranking | sector evidence row fields |
| `limit_up_count` | limit-up pool sector distribution | sector evidence row fields |
| `high_anchor_height`, `high_anchor_name` | consecutive-board ladder / limit-up pool | sector evidence row fields |
| `broad_rally_pct` | sector component breadth | missing allowed |
| `strong_gain_count` | sector member gain distribution | sector evidence row fields |
| `turnover_share_pct`, `turnover_share_change` | mainline turnover-share trend | sector evidence row fields |

Missing fields must be recorded in `missing_fields`; do not convert missing values into fake zero precision.

## Task 1: Runtime Classification Helper

**Files:**
- Create: `tests/test_mainline_attack_evidence_runtime.py`
- Modify: `scripts/domains/market_state/mainline_turnover_summary_runtime.py`

- [ ] **Step 1: Write failing tests for six calibration samples**

Create `tests/test_mainline_attack_evidence_runtime.py`:

```python
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class MainlineAttackEvidenceRuntimeTest(unittest.TestCase):
    def _load_module(self):
        return importlib.import_module("domains.market_state.mainline_turnover_summary_runtime")

    def test_confirmed_single_mainline_requires_fund_and_strength_evidence(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 42.5,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "high_anchor_name": "中船特气",
                    "broad_rally_pct": 72.0,
                    "strong_gain_count": 18,
                    "turnover_share_pct": 12.4,
                    "turnover_share_change": 1.6,
                },
                {
                    "sector_name": "电力",
                    "net_inflow_amount": 8.0,
                    "net_inflow_rank": 5,
                    "limit_up_count": 2,
                    "high_anchor_height": 2,
                    "turnover_share_pct": 7.1,
                    "turnover_share_change": -0.4,
                },
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], [])
        self.assertIn("资金净流入靠前", summary["evidence_labels"])
        self.assertIn("批量涨停", summary["evidence_labels"])
        self.assertIn("高标强度突出", summary["evidence_labels"])
        self.assertIn("成交占比扩张", summary["evidence_labels"])
        self.assertEqual(summary["evidence_gaps"], [])
        self.assertEqual(summary["confirmation_evidence"], "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张")

    def test_double_line_competition_when_two_sectors_have_cross_validated_attack(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 35.0, "net_inflow_rank": 1, "limit_up_count": 7, "high_anchor_height": 4},
                {"sector_name": "电力", "net_inflow_amount": 30.0, "net_inflow_rank": 2, "limit_up_count": 6, "high_anchor_height": 3},
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertEqual(summary["relationship_hint"], "双主线竞争")

    def test_chaotic_rotation_when_three_local_hotspots_have_no_clear_winner(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 12.0, "net_inflow_rank": 3, "limit_up_count": 2},
                {"sector_name": "电力", "net_inflow_amount": 11.0, "net_inflow_rank": 4, "high_anchor_height": 2},
                {"sector_name": "化学制品", "net_inflow_amount": 9.0, "net_inflow_rank": 5, "strong_gain_count": 8},
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "chaotic_rotation")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["半导体", "电力", "化学制品"])
        self.assertEqual(summary["relationship_hint"], "混沌接力")
        self.assertIn("多方向局部活跃但资金未明显胜出", summary["confirmation_evidence"])

    def test_no_attack_when_evidence_is_distributed_and_weak(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "机器人", "net_inflow_amount": 2.0, "net_inflow_rank": 12, "limit_up_count": 1, "turnover_share_change": -0.2},
                {"sector_name": "军工", "net_inflow_amount": -1.0, "net_inflow_rank": 24, "limit_up_count": 0},
            ],
            market_regime="弱市",
        )

        self.assertEqual(summary["attack_state"], "no_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], [])
        self.assertEqual(summary["confirmation_evidence"], "资金未形成明确进攻方向")

    def test_limit_up_without_fund_support_is_candidate_not_confirmed(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "电力", "net_inflow_amount": -6.0, "net_inflow_rank": 28, "limit_up_count": 9, "high_anchor_height": 4}
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "candidate_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertIn("情绪强于资金确认", summary["evidence_gaps"])

    def test_fund_probe_without_strength_support_is_candidate_not_confirmed(self):
        runtime = self._load_module()

        summary = runtime.build_mainline_attack_evidence_summary(
            sector_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 50.0, "net_inflow_rank": 1, "limit_up_count": 1, "high_anchor_height": 1, "broad_rally_pct": 42.0}
            ],
            market_regime="震荡",
        )

        self.assertEqual(summary["attack_state"], "candidate_attack")
        self.assertEqual(summary["primary_line"], "")
        self.assertEqual(summary["candidate_lines"], ["半导体"])
        self.assertIn("资金试探但强度不足", summary["evidence_gaps"])
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_mainline_attack_evidence_runtime -v
```

Expected: FAIL because `build_mainline_attack_evidence_summary` does not exist.

- [ ] **Step 3: Add minimal classification helpers**

In `scripts/domains/market_state/mainline_turnover_summary_runtime.py`, update `__all__`:

```python
__all__ = [
    "build_mainline_attack_evidence_summary",
    "build_mainline_turnover_summary",
    "should_rebuild_mainline_turnover_summary",
]
```

Add these helpers above `build_mainline_turnover_summary`:

```python
def _normalize_sector_evidence_row(row):
    row = row or {}
    sector = str(row.get("sector_name") or row.get("sector") or "").strip()
    normalized = {
        "sector_name": sector,
        "net_inflow_amount": _safe_float(row.get("net_inflow_amount")),
        "net_inflow_rank": int(_safe_float(row.get("net_inflow_rank"), 999)),
        "limit_up_count": int(_safe_float(row.get("limit_up_count"))),
        "high_anchor_height": int(_safe_float(row.get("high_anchor_height"))),
        "high_anchor_name": str(row.get("high_anchor_name") or "").strip(),
        "broad_rally_pct": _safe_float(row.get("broad_rally_pct"), -1.0),
        "strong_gain_count": int(_safe_float(row.get("strong_gain_count"))),
        "turnover_share_pct": _safe_float(row.get("turnover_share_pct")),
        "turnover_share_change": _safe_float(row.get("turnover_share_change")),
    }
    missing = []
    for key in ("net_inflow_amount", "net_inflow_rank", "limit_up_count", "high_anchor_height", "broad_rally_pct", "strong_gain_count", "turnover_share_pct", "turnover_share_change"):
        if row.get(key) in (None, ""):
            missing.append(key)
    normalized["missing_fields"] = missing
    normalized["evidence_labels"] = _sector_evidence_labels(normalized)
    normalized["fund_evidence_count"] = len([label for label in normalized["evidence_labels"] if label in ("资金净流入靠前", "资金净流入明显领先", "成交占比扩张")])
    normalized["strength_evidence_count"] = len([label for label in normalized["evidence_labels"] if label in ("批量涨停", "高标强度突出", "板块普涨", "高涨幅集群")])
    normalized["evidence_count"] = normalized["fund_evidence_count"] + normalized["strength_evidence_count"]
    return normalized


def _sector_evidence_labels(row):
    labels = []
    if row["net_inflow_amount"] > 0 and row["net_inflow_rank"] <= 3:
        labels.append("资金净流入靠前")
    if row["net_inflow_amount"] >= 30 and row["net_inflow_rank"] == 1:
        labels.append("资金净流入明显领先")
    if row["limit_up_count"] >= 5:
        labels.append("批量涨停")
    if row["high_anchor_height"] >= 3:
        labels.append("高标强度突出")
    if row["broad_rally_pct"] >= 65:
        labels.append("板块普涨")
    if row["strong_gain_count"] >= 10:
        labels.append("高涨幅集群")
    if row["turnover_share_change"] >= 1.0:
        labels.append("成交占比扩张")
    return labels


def _rank_sector_evidence(rows):
    return sorted(
        rows,
        key=lambda row: (
            row["fund_evidence_count"] > 0 and row["strength_evidence_count"] > 0,
            row["evidence_count"],
            row["net_inflow_amount"],
            -row["net_inflow_rank"],
            row["limit_up_count"],
        ),
        reverse=True,
    )


def _is_confirmed_attack(row):
    return row["fund_evidence_count"] > 0 and row["strength_evidence_count"] > 0


def _is_candidate_attack(row):
    return row["evidence_count"] > 0


def _candidate_gap(row):
    if row["strength_evidence_count"] > 0 and row["fund_evidence_count"] == 0:
        return "情绪强于资金确认"
    if row["fund_evidence_count"] > 0 and row["strength_evidence_count"] == 0:
        return "资金试探但强度不足"
    return ""


def _confirmation_text(primary, labels):
    pieces = []
    if "资金净流入明显领先" in labels:
        pieces.append("资金净流入明显领先")
    elif "资金净流入靠前" in labels:
        pieces.append("资金净流入靠前")
    strength_parts = []
    if "批量涨停" in labels:
        strength_parts.append("涨停")
    if "高标强度突出" in labels:
        strength_parts.append("高标")
    if strength_parts:
        pieces.append("和".join(strength_parts) + "更集中")
    if "板块普涨" in labels:
        pieces.append("板块普涨")
    if "高涨幅集群" in labels:
        pieces.append("高涨幅集群")
    if "成交占比扩张" in labels:
        pieces.append("成交占比扩张")
    return f"{primary}" + "，".join(pieces) if pieces else f"{primary}主线确认依据待补充"


def build_mainline_attack_evidence_summary(*, sector_evidence_rows=None, market_regime=""):
    rows = [
        _normalize_sector_evidence_row(row)
        for row in (sector_evidence_rows or [])
        if str((row or {}).get("sector_name") or (row or {}).get("sector") or "").strip()
    ]
    ranked = _rank_sector_evidence(rows)
    confirmed = [row for row in ranked if _is_confirmed_attack(row)]
    candidates = [row for row in ranked if not _is_confirmed_attack(row) and _is_candidate_attack(row)]
    if confirmed:
        primary = confirmed[0]
        other_confirmed = [row["sector_name"] for row in confirmed[1:]]
        relationship_hint = "双主线竞争" if other_confirmed else "单主线聚焦"
        return {
            "attack_state": "confirmed_attack",
            "primary_line": primary["sector_name"],
            "candidate_lines": other_confirmed,
            "background_lines": [row["sector_name"] for row in candidates[:2]],
            "relationship_hint": relationship_hint,
            "evidence_labels": primary["evidence_labels"],
            "confirmation_evidence": _confirmation_text(primary["sector_name"], primary["evidence_labels"]),
            "evidence_gaps": [],
            "sector_evidence_rows": ranked,
        }
    if len(candidates) >= 3:
        return {
            "attack_state": "chaotic_rotation",
            "primary_line": "",
            "candidate_lines": [row["sector_name"] for row in candidates[:3]],
            "background_lines": [],
            "relationship_hint": "混沌接力",
            "evidence_labels": [],
            "confirmation_evidence": "多方向局部活跃但资金未明显胜出",
            "evidence_gaps": [],
            "sector_evidence_rows": ranked,
        }
    if candidates:
        gaps = [gap for row in candidates for gap in [_candidate_gap(row)] if gap]
        return {
            "attack_state": "candidate_attack",
            "primary_line": "",
            "candidate_lines": [row["sector_name"] for row in candidates],
            "background_lines": [],
            "relationship_hint": "候选线",
            "evidence_labels": candidates[0]["evidence_labels"],
            "confirmation_evidence": f"{candidates[0]['sector_name']}有局部进攻证据，但主线确认不足",
            "evidence_gaps": gaps,
            "sector_evidence_rows": ranked,
        }
    return {
        "attack_state": "no_attack",
        "primary_line": "",
        "candidate_lines": [],
        "background_lines": [],
        "relationship_hint": "无主线",
        "evidence_labels": [],
        "confirmation_evidence": "资金未形成明确进攻方向",
        "evidence_gaps": [],
        "sector_evidence_rows": ranked,
    }
```

- [ ] **Step 4: Run the focused runtime tests**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests.test_mainline_attack_evidence_runtime -v
```

Expected: PASS.

## Task 2: Integrate Attack Evidence Into Capacity/Regime Runtime

**Files:**
- Modify: `scripts/domains/market_state/mainline_turnover_summary_runtime.py`
- Test: `tests/test_mainline_turnover_summary_runtime.py`

- [ ] **Step 1: Add failing tests for integration and compatibility**

Append these tests to `MainlineTurnoverSummaryRuntimeTest` in `tests/test_mainline_turnover_summary_runtime.py`:

```python
    def test_build_mainline_turnover_summary_uses_attack_evidence_for_confirmation(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "电力"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={
                "date": "2026-05-15",
                "sector_name": "半导体",
                "total_turnover": 30000.0,
                "turnover_share_pct": 12.4,
            },
            recent_sector_turnover_history=[],
            sector_attack_evidence_rows=[
                {
                    "sector_name": "半导体",
                    "net_inflow_amount": 45.0,
                    "net_inflow_rank": 1,
                    "limit_up_count": 8,
                    "high_anchor_height": 4,
                    "turnover_share_change": 1.3,
                }
            ],
        )

        self.assertEqual(result["mainline_attack_evidence_summary"]["attack_state"], "confirmed_attack")
        self.assertEqual(result["mainline_capacity_regime_summary"]["primary_line"], "半导体")
        self.assertEqual(
            result["mainline_capacity_regime_summary"]["confirmation_evidence"],
            "半导体资金净流入靠前，涨停和高标更集中，成交占比扩张",
        )

    def test_build_mainline_turnover_summary_does_not_confirm_primary_mainline_without_attack_evidence(self):
        runtime = self._load_module()

        result = runtime.build_mainline_turnover_summary(
            target_date="2026-05-15",
            current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "半导体"},
            recent_mainline_history=[],
            current_sector_turnover_snapshot={"date": "2026-05-15", "sector_name": "半导体", "total_turnover": 26000.0},
            recent_sector_turnover_history=[],
            sector_attack_evidence_rows=[
                {"sector_name": "半导体", "net_inflow_amount": 2.0, "net_inflow_rank": 20, "limit_up_count": 0}
            ],
        )

        self.assertEqual(result["mainline_attack_evidence_summary"]["attack_state"], "no_attack")
        self.assertEqual(result["mainline_capacity_regime_summary"]["mainline_regime"], "无主线")
        self.assertEqual(result["mainline_capacity_regime_summary"]["primary_line"], "暂无")
        self.assertEqual(result["mainline_capacity_regime_summary"]["confirmation_evidence"], "资金未形成明确进攻方向")
```

- [ ] **Step 2: Run the integration tests and verify they fail**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_mainline_turnover_summary_runtime.MainlineTurnoverSummaryRuntimeTest.test_build_mainline_turnover_summary_uses_attack_evidence_for_confirmation \
  tests.test_mainline_turnover_summary_runtime.MainlineTurnoverSummaryRuntimeTest.test_build_mainline_turnover_summary_does_not_confirm_primary_mainline_without_attack_evidence \
  -v
```

Expected: FAIL because `build_mainline_turnover_summary` does not accept `sector_attack_evidence_rows`.

- [ ] **Step 3: Thread attack evidence into the builder**

In `scripts/domains/market_state/mainline_turnover_summary_runtime.py`, change the function signature:

```python
def build_mainline_turnover_summary(
    *,
    target_date="",
    current_mainline_history_record=None,
    recent_mainline_history=None,
    current_sector_turnover_snapshot=None,
    recent_sector_turnover_history=None,
    sector_attack_evidence_rows=None,
):
```

Before building `capacity_regime_summary`, add:

```python
    attack_evidence_summary = build_mainline_attack_evidence_summary(
        sector_evidence_rows=sector_attack_evidence_rows,
        market_regime=current_record.get("market_regime"),
    ) if sector_attack_evidence_rows is not None else {}
    evidence_primary_line = str((attack_evidence_summary or {}).get("primary_line") or "").strip()
    evidence_relationship = str((attack_evidence_summary or {}).get("relationship_hint") or "").strip()
    current_mainline_for_regime = evidence_primary_line if attack_evidence_summary else current_mainline
    current_record_for_regime = dict(current_record)
    if attack_evidence_summary:
        current_record_for_regime["mainline_confirmation_evidence"] = attack_evidence_summary.get("confirmation_evidence") or ""
        if evidence_relationship in ("混沌接力", "双主线竞争"):
            current_record_for_regime["sector_relationship_state"] = evidence_relationship
        if attack_evidence_summary.get("attack_state") in ("no_attack", "chaotic_rotation"):
            current_mainline_for_regime = ""
```

Then change the capacity builder call to:

```python
    capacity_regime_summary = _build_mainline_capacity_regime_summary(
        current_mainline=current_mainline_for_regime,
        current_record=current_record_for_regime,
        current_snapshot=current_snapshot,
        recent_sector_turnover_history=recent_sector_turnover_history,
        action_text=action_text,
    )
```

Add this key to the return payload:

```python
        "mainline_attack_evidence_summary": attack_evidence_summary,
```

- [ ] **Step 4: Run runtime tests**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_mainline_attack_evidence_runtime \
  tests.test_mainline_turnover_summary_runtime \
  -v
```

Expected: PASS.

## Task 3: Support Resolver And Reasoning Packet

**Files:**
- Modify: `scripts/report/mainline_turnover_summary_support.py`
- Modify: `scripts/report/reasoning_decision_support.py`
- Test: `tests/test_mainline_turnover_summary_support.py`
- Test: `tests/test_reasoning_decision_support.py`

- [ ] **Step 1: Add failing support resolver test**

Append to `tests/test_mainline_turnover_summary_support.py`:

```python
    def test_resolve_mainline_attack_evidence_summary_from_nested_turnover_summary(self):
        from report.mainline_turnover_summary_support import resolve_mainline_attack_evidence_summary

        summary = resolve_mainline_attack_evidence_summary(
            {
                "mainline_turnover_summary": {
                    "mainline_attack_evidence_summary": {
                        "attack_state": "confirmed_attack",
                        "primary_line": "半导体",
                        "candidate_lines": ["电力"],
                        "background_lines": ["化学制品"],
                        "relationship_hint": "双主线竞争",
                        "evidence_labels": ["资金净流入靠前", "批量涨停"],
                        "confirmation_evidence": "半导体资金净流入靠前，涨停更集中",
                        "evidence_gaps": [],
                    }
                }
            }
        )

        self.assertEqual(summary["attack_state"], "confirmed_attack")
        self.assertEqual(summary["primary_line"], "半导体")
        self.assertEqual(summary["candidate_lines"], ["电力"])
        self.assertEqual(summary["background_lines"], ["化学制品"])
```

- [ ] **Step 2: Add failing reasoning packet test**

In `tests/test_reasoning_decision_support.py`, add to the existing stable packet test or add a new test:

```python
    def test_reasoning_input_packet_includes_mainline_attack_evidence_summary(self):
        packet = build_reasoning_input_packet(
            {
                "market_research_snapshot": {
                    "mainline_turnover_summary": {
                        "mainline_attack_evidence_summary": {
                            "attack_state": "confirmed_attack",
                            "primary_line": "半导体",
                            "candidate_lines": ["电力"],
                            "background_lines": [],
                            "relationship_hint": "双主线竞争",
                            "evidence_labels": ["资金净流入靠前", "批量涨停"],
                            "confirmation_evidence": "半导体资金净流入靠前，涨停更集中",
                            "evidence_gaps": [],
                        }
                    }
                }
            }
        )

        self.assertEqual(
            packet["mainline_snapshot"]["mainline_attack_evidence_summary"]["primary_line"],
            "半导体",
        )
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_mainline_turnover_summary_support \
  tests.test_reasoning_decision_support \
  -v
```

Expected: FAIL because the resolver and packet key do not exist yet.

- [ ] **Step 4: Add resolver**

In `scripts/report/mainline_turnover_summary_support.py`, add above `resolve_mainline_capacity_regime_summary`:

```python
def _string_list(value):
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.replace("，", ",").split(",") if part.strip()]


def resolve_mainline_attack_evidence_summary(context=None):
    context = context or {}
    source = dict(context.get("mainline_attack_evidence_summary") or {})
    if not source:
        source = dict((context.get("mainline_turnover_summary") or {}).get("mainline_attack_evidence_summary") or {})
    if not source:
        return {}
    return {
        "attack_state": str(source.get("attack_state") or "-").strip() or "-",
        "primary_line": str(source.get("primary_line") or "").strip(),
        "candidate_lines": _string_list(source.get("candidate_lines")),
        "background_lines": _string_list(source.get("background_lines")),
        "relationship_hint": str(source.get("relationship_hint") or "-").strip() or "-",
        "evidence_labels": _string_list(source.get("evidence_labels")),
        "confirmation_evidence": str(source.get("confirmation_evidence") or "-").strip() or "-",
        "evidence_gaps": _string_list(source.get("evidence_gaps")),
    }
```

- [ ] **Step 5: Add reasoning packet key**

In `scripts/report/reasoning_decision_support.py`, update the import:

```python
from report.mainline_turnover_summary_support import (
    resolve_mainline_attack_evidence_summary,
    resolve_mainline_capacity_regime_summary,
)
```

Where the reasoning packet builds `mainline_snapshot`, add:

```python
            "mainline_attack_evidence_summary": resolve_mainline_attack_evidence_summary(snapshot),
```

- [ ] **Step 6: Run support and reasoning tests**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_mainline_turnover_summary_support \
  tests.test_reasoning_decision_support \
  -v
```

Expected: PASS.

## Task 4: Acceptance And Regression Verification

**Files:**
- No production files unless tests expose a gap.

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest \
  tests.test_mainline_attack_evidence_runtime \
  tests.test_mainline_turnover_summary_support \
  tests.test_mainline_turnover_summary_runtime \
  tests.test_front_summary_renderer \
  tests.test_front_page_v2_renderer \
  tests.test_market_research_renderer \
  tests.test_reasoning_decision_support \
  tests.test_report_acceptance_audit \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run forbidden wording scan**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

targets = [
    Path("scripts"),
    Path("tests"),
    Path("docs/trellis/specs/2026-05-15-mainline-attack-evidence-structure-design.md"),
]
parts = [("90", "00e"), ("1", ".5w"), ("2", "w"), ("门", "禁")]
old_headers = [
    "| 周期主线 | 当天主攻线 | 两者关系 | 明日动作 |",
    "### 4. 双层主线结论",
]
for target in targets:
    paths = target.rglob("*") if target.is_dir() else [target]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for left, right in parts:
            if left + right in text:
                print(f"{path}: contains forbidden wording")
        for header in old_headers:
            if header in text:
                print(f"{path}: contains retired mainline surface")
PY
```

Expected: no matches in `scripts/` except explicit audit constants or negative tests. No matches for experience anchors or forbidden wording.

- [ ] **Step 3: Check compatibility output manually**

Run:

```bash
/Users/chaixixi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 - <<'PY'
from domains.market_state.mainline_turnover_summary_runtime import build_mainline_turnover_summary

result = build_mainline_turnover_summary(
    target_date="2026-05-15",
    current_mainline_history_record={"date": "2026-05-15", "primary_mainline": "半导体"},
    current_sector_turnover_snapshot={"date": "2026-05-15", "sector_name": "半导体", "total_turnover": 30000.0, "turnover_share_pct": 12.4},
    recent_sector_turnover_history=[],
)
print(result["mainline_capacity_regime_summary"]["primary_line"])
print(result.get("mainline_attack_evidence_summary"))
PY
```

Expected:

```text
半导体
{}
```

This confirms old callers without structured evidence still behave as before.

## Self-review Checklist

- Spec coverage:
  - Evidence fields: Task 1 normalization.
  - Four required outcomes plus two edge samples: Task 1 tests.
  - Confirmation evidence generated from structured fields: Task 1 and Task 2.
  - Integration with `mainline_capacity_regime_summary`: Task 2.
  - Compatibility path preserved: Task 2 and Task 4.
  - Reasoning reuse: Task 3.
- Placeholder scan:
  - No `TBD`, `TODO`, `implement later`, or vague "add tests" steps.
- Type consistency:
  - Summary key is `mainline_attack_evidence_summary` everywhere.
  - Classification values are `confirmed_attack`, `candidate_attack`, `chaotic_rotation`, `no_attack`.
  - List fields are `candidate_lines`, `background_lines`, `evidence_labels`, and `evidence_gaps`.
