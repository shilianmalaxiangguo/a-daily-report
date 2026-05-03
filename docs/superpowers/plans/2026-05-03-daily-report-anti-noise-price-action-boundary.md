# Daily Report Anti-Noise Price Action Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the approved anti-noise and price-action boundary visible to future report work, inherited by the report contract, and enforceable by the report acceptance audit.

**Architecture:** Keep the boundary lightweight: documentation routes own the concept, and the existing markdown acceptance audit blocks obvious user-facing violations. No MiroFish integration, no new report section, and no price-action calculation module is added in this plan; future feature specs can implement fields such as slope and retracement after this boundary is protected.

**Tech Stack:** Markdown skill references, Python standard library, existing `scripts/report/report_acceptance_audit.py`, `unittest`, `git diff --check`.

---

## File Structure

- Modify: `SKILL.md`
  - Add the anti-noise boundary spec to the skill references and operating rules so future natural-language optimization asks inherit it.
- Modify: `references/report-contract.md`
  - Add the anti-noise and price-action inheritance contract: external simulations stay out of the main chain; experience enters only as price-action fields.
- Modify: `tests/test_daily_report_skill_docs.py`
  - Add a docs test that protects the new boundary reference and wording.
- Modify: `scripts/report/report_acceptance_audit.py`
  - Add a small front-page audit that rejects obvious simulation/noise phrases and theory-driven buy language.
- Modify: `tests/test_report_acceptance_audit.py`
  - Add tests for rejected noisy simulation wording and allowed field-based price-action wording.

---

### Task 1: Route the Anti-Noise Boundary Through Skill Docs

**Files:**
- Modify: `SKILL.md`
- Modify: `references/report-contract.md`
- Modify: `tests/test_daily_report_skill_docs.py`

- [x] **Step 1: Write the failing docs test**

Add this test method to `tests/test_daily_report_skill_docs.py` inside `DailyReportSkillDocsTest`:

```python
    def test_skill_and_report_contract_inherit_anti_noise_price_action_boundary(self):
        skill = self._read("SKILL.md")
        report_contract = self._read("references/report-contract.md")
        boundary_spec = self._read(
            "docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md"
        )
        combined = "\n".join([skill, report_contract, boundary_spec])

        for required in [
            "2026-05-03-daily-report-anti-noise-price-action-boundary-design.md",
            "推演型工具不得进入日报主链",
            "交易经验可以被吸收，但必须字段化、规则化、复盘化",
            "价格行为字段",
            "上涨斜率",
            "回撤比例",
            "突破后承接",
            "加速后衰竭",
            "不能以自由叙事进入日报主链",
        ]:
            self.assertIn(required, combined)
```

- [x] **Step 2: Run the docs test and verify it fails**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs
```

Expected: FAIL because `SKILL.md` and `references/report-contract.md` do not yet mention the new boundary spec or its inheritance wording.

- [x] **Step 3: Update `SKILL.md` routing and operating rules**

In `SKILL.md`, update the `optimize_skill` row in the intent table so the first reference chain includes the boundary spec after `references/report-contract.md`:

```markdown
| `optimize_skill` | User asks to improve this skill, routing, references, the report contract, or the report workflow. | `references/report-contract.md`, then `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md`, then `references/reasoning-mode-contract.md`, then `references/memory-governance.md`, then `references/verification.md` |
```

Add this bullet to the `## Operating Rules` list after the existing reasoning-contract bullet:

```markdown
- Treat external simulations and free-form predictions as anti-noise boundary risks: they do not enter the report main chain unless a later approved spec turns them into auditable fields. Trading experience can be absorbed only after being translated into price-action fields such as `上涨斜率`, `回撤比例`, `突破后承接`, and `加速后衰竭`.
```

Add this reference bullet to the `## References` list:

```markdown
- `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md` - anti-noise boundary for simulation tools and price-action fieldization.
```

- [x] **Step 4: Update `references/report-contract.md` inheritance rules**

In `references/report-contract.md`, add this bullet to `## Future Change Inheritance`:

```markdown
- Future report changes also inherit `docs/superpowers/specs/2026-05-03-daily-report-anti-noise-price-action-boundary-design.md`: simulation tools stay out of the main chain, and trading experience enters only after becoming price-action fields.
```

Add this section after `## User-Facing Contract`:

```markdown
## Anti-Noise And Price-Action Boundary

- Do not add external simulation, multi-agent, or free-form prediction language to the report front page.
- Do not use theory words such as `能量学`, `能量释放`, or `群体行为共振` as the reason for buy, add, or upgrade actions.
- Experience is allowed only after fieldization: prefer `上涨斜率`, `回撤比例`, `突破后承接`, `加速后衰竭`, `波动收敛`, and `板块内扩散强度`.
- Price-action fields may support candidate qualification, failure conditions, and unique action wording, but they must not bypass mainline confirmation, entry permission, 60分钟 confirmation, or 30分钟 stop rules.
```

- [x] **Step 5: Run docs tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs
```

Expected: PASS.

- [x] **Step 6: Commit Task 1**

Run:

```bash
git add SKILL.md references/report-contract.md tests/test_daily_report_skill_docs.py
git commit -m "docs: route anti-noise report boundary"
```

---

### Task 2: Add Report Acceptance Audit Guardrails

**Files:**
- Modify: `scripts/report/report_acceptance_audit.py`
- Modify: `tests/test_report_acceptance_audit.py`

- [x] **Step 1: Write failing audit tests**

Add these test methods to `ReportAcceptanceAuditTest` in `tests/test_report_acceptance_audit.py`:

```python
    def test_audit_flags_front_page_simulation_noise_language(self):
        noisy_phrases = [
            "多智能体一致认为主线明天会修复。",
            "沙盘推演显示半导体可能爆发。",
            "模型认为胜率提高，所以明天提高仓位。",
            "虽然规则未满足，但推演偏乐观，可以先买。",
        ]

        for phrase in noisy_phrases:
            with self.subTest(phrase=phrase):
                bad = GOOD_MARKDOWN.replace(
                    "## 七、最终结论",
                    f"{phrase}\n\n## 七、最终结论",
                )

                result = audit_report_markdown(bad)

                self.assertIn("simulation_noise_language", {finding["code"] for finding in result["findings"]})
                self.assertFalse(result["passed"])

    def test_audit_flags_theory_driven_buy_language(self):
        bad = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            "能量释放，所以可以买；群体行为共振，所以提高仓位。\n\n## 七、最终结论",
        )

        result = audit_report_markdown(bad)

        self.assertIn("theory_driven_action_language", {finding["code"] for finding in result["findings"]})
        self.assertFalse(result["passed"])

    def test_audit_allows_fieldized_price_action_language(self):
        report = GOOD_MARKDOWN.replace(
            "## 七、最终结论",
            "上涨斜率强，但回撤比例仍需验证；放量突破后先看承接，不追高；加速后出现衰竭风险，明天不主动追。\n\n## 七、最终结论",
        )

        result = audit_report_markdown(report)

        self.assertTrue(result["passed"], result["findings"])
```

- [x] **Step 2: Run audit tests and verify they fail**

Run:

```bash
venv/bin/python -m unittest tests.test_report_acceptance_audit
```

Expected: FAIL because the new findings are not implemented yet.

- [x] **Step 3: Add forbidden phrase constants**

In `scripts/report/report_acceptance_audit.py`, after `REASONING_CHAIN_LEAK_MARKERS`, add:

```python
SIMULATION_NOISE_MARKERS = (
    "多智能体一致认为",
    "沙盘推演显示",
    "某情景下可能爆发",
    "模型认为胜率提高",
    "综合模拟后建议买入",
    "虽然规则未满足，但推演偏乐观",
)

THEORY_ACTION_MARKERS = (
    "能量释放，所以可以买",
    "能量释放，所以可以加仓",
    "能量释放，所以提高仓位",
    "群体行为共振，所以可以买",
    "群体行为共振，所以可以加仓",
    "群体行为共振，所以提高仓位",
)
```

- [x] **Step 4: Add the audit helper**

In `scripts/report/report_acceptance_audit.py`, add this helper after `_audit_reasoning_surface`:

```python
def _audit_anti_noise_language(lines):
    findings = []
    front = _front_page_lines(lines)
    for index, line in enumerate(front, 1):
        text = str(line)
        for marker in SIMULATION_NOISE_MARKERS:
            if marker in text:
                findings.append(
                    _finding(
                        "simulation_noise_language",
                        f"front page must not use simulation/noise phrase: {marker}",
                        line=index,
                    )
                )
        for marker in THEORY_ACTION_MARKERS:
            if marker in text:
                findings.append(
                    _finding(
                        "theory_driven_action_language",
                        f"front page must not use theory language as an action reason: {marker}",
                        line=index,
                    )
                )
    return findings
```

- [x] **Step 5: Wire the helper into the audit**

In `audit_report_markdown()`, add the helper after `_audit_reasoning_surface(lines)` and before `_audit_unique_focus(lines)`:

```python
    findings.extend(_audit_anti_noise_language(lines))
```

- [x] **Step 6: Run audit tests and verify they pass**

Run:

```bash
venv/bin/python -m unittest tests.test_report_acceptance_audit
```

Expected: PASS.

- [x] **Step 7: Commit Task 2**

Run:

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "test: audit anti-noise report language"
```

---

### Task 3: Verify the Boundary End-to-End

**Files:**
- No new files expected.
- Verify: `SKILL.md`
- Verify: `references/report-contract.md`
- Verify: `scripts/report/report_acceptance_audit.py`
- Verify: `tests/test_daily_report_skill_docs.py`
- Verify: `tests/test_report_acceptance_audit.py`

- [x] **Step 1: Run focused docs and audit tests**

Run:

```bash
venv/bin/python -m unittest tests.test_daily_report_skill_docs tests.test_report_acceptance_audit
```

Expected: PASS.

- [x] **Step 2: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [x] **Step 3: Inspect changed files for boundary wording**

Run:

```bash
rg -n "anti-noise|反噪音|价格行为|上涨斜率|回撤比例|突破后承接|加速后衰竭|simulation_noise_language|theory_driven_action_language" SKILL.md references/report-contract.md scripts/report/report_acceptance_audit.py tests/test_daily_report_skill_docs.py tests/test_report_acceptance_audit.py
```

Expected: matches in the skill docs, report contract, audit code, and tests.

- [x] **Step 4: Check working tree status**

Run:

```bash
git status --short
```

Expected: clean working tree after Task 1 and Task 2 commits.

---

## Self-Review

Spec coverage:

- MiroFish and simulation tools stay out of the main chain: Task 1 documents inheritance, Task 2 audits obvious simulation language.
- Trading experience enters only after fieldization: Task 1 adds the report-contract boundary with price-action fields.
- User-visible output avoids theory-driven action language: Task 2 rejects the clearest front-page violations.
- No MiroFish interface, no new section, no price-action computation: this plan intentionally avoids all three.

No placeholders:

- Each task names exact files, exact code snippets, commands, and expected results.
- The plan does not use `TBD`, `TODO`, or “similar to” instructions.

Type and naming consistency:

- New finding codes are `simulation_noise_language` and `theory_driven_action_language`.
- The audit helper name is `_audit_anti_noise_language`.
- The test assertions use the same finding codes.


## Execution Record

Completed in current worktree `/Users/chaixixi/.codex/worktrees/c89b/a-daily-report` on branch `codex/anti-noise-price-action-boundary`.

Commits produced by this plan:

- `dfe9191 docs: route anti-noise report boundary`
- `e68cd91 test: audit anti-noise report language`

Verification run after implementation:

```bash
python3 -m unittest tests.test_daily_report_skill_docs tests.test_report_acceptance_audit
# Ran 27 tests ... OK

git diff --check
# no output
```

Main-tree merge was intentionally not performed from this worktree because the main `develop` tree has unrelated uncommitted changes. This worktree branch remains the merge source.
