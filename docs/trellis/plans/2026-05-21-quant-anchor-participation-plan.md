# Quant Anchor Participation Implementation Plan

> **For agentic workers:** REQUIRED WORKFLOW: Use Trellis task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add quant/psychological price-anchor logic to the LLM Wiki, planned participation fields, and daily-report display without turning pair-number anchors into standalone buy reasons.

**Architecture:** Extend the existing LLM Wiki and compact context first, then add optional participation-script fields that preserve current enums and old consumers. Render those fields as short action text in the existing conviction-list section rather than adding a new report table.

**Tech Stack:** Python 3.14 via `.generated/venv-py314/bin/python3.14`, unittest, Markdown wiki/spec files, existing report selection and decision-ledger modules.

---

## File Map

- Modify `wiki/交易思想/价格行为与能量框架.md`: add `心理价位与量化锚点` rules.
- Modify `wiki/交易思想/极度看好参与时机.md`: expand common selection consistency to include quant momentum and hidden liquidity.
- Modify `scripts/knowledge/llm_wiki_context.py`: expose compact field mappings and digest phrases.
- Modify `tests/test_llm_wiki_context.py`: protect compact context and digest.
- Modify `scripts/selection/candidate_execution_contracts.py`: build optional quant-anchor plan fields from candidates.
- Modify `scripts/report/decision_ledger.py`: normalize and preserve quant-anchor fields in `planned_participation`.
- Modify `tests/test_decision_ledger.py`: verify fields are preserved and old planned participation fields still work.
- Modify `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`: render a short quant-anchor action column in the existing participation script table.
- Modify `tests/test_execution_chain_step1_sections.py` or `tests/test_candidate_selection_stage.py`: verify the rendered report shows concise action text.
- Optional modify `tests/test_selection_trend_runtime.py`: verify quant-anchor fields do not upgrade a candidate into primary ranking by themselves if this is simple to express with existing fixtures.

## Task 1: Wiki And Compact Context

**Files:**
- Modify: `wiki/交易思想/价格行为与能量框架.md`
- Modify: `wiki/交易思想/极度看好参与时机.md`
- Modify: `scripts/knowledge/llm_wiki_context.py`
- Test: `tests/test_llm_wiki_context.py`

- [ ] **Step 1: Add failing LLM wiki context assertions**

Add assertions to `tests/test_llm_wiki_context.py`:

```python
self.assertIn("心理价位与量化锚点 -> 对子数、整数位、前高前低、VWAP、MA和成交密集区只作价格锚点，不作独立买入理由", context["field_mappings"])
self.assertIn("隐藏买卖盘 -> 顶部锚点冲不过按隐藏卖盘和止盈观察，底部锚点必须站回VWAP并完成10点确认才允许试错", context["field_mappings"])
self.assertIn("量化共同选择 -> 昨日持筹者、明日新买盘、主线资金、量化动量四方一致后才提高参与质量", context["field_mappings"])
self.assertIn("高潮反包 -> 高潮后反包优先按先手兑现点，放量吃掉压力并回踩不破才恢复候选", context["field_mappings"])
```

In the digest test, add:

```python
self.assertIn("对子数整数位只作价格锚点", digest)
self.assertIn("顶部冲不过先止盈", digest)
self.assertIn("底部站回VWAP和10点确认才试错", digest)
self.assertIn("反包先按兑现点", digest)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context
```

Expected: fail because new field mappings and digest text are not present.

- [ ] **Step 3: Update wiki documents**

In `wiki/交易思想/价格行为与能量框架.md`, after the `买点卖点底层操作逻辑` section and before `龙头速度档与均线角色`, add:

```markdown
### 心理价位与量化锚点

对子数、整数位、前高前低、涨停价、VWAP、MA 和成交密集区，都属于价格锚点。锚点只说明市场可能在这里集中反应，不说明一定能买或一定会涨。

对子数不是孤立价格，而是给 VWAP、MA3、MA5、MA10、MA20、区间上下沿和前高前低打辅助。它更像隐藏买卖盘留下的痕迹：顶部冲不过，说明场外待卖力量可能比想象中大；底部跌不破，说明潜在承接可能存在，但仍要等价格确认。

判断规则：

- 先看锚点位置：区间顶部偏卖压，区间底部偏承接观察，中间位置多数只是噪音。
- 再看锚点共振：对子数或整数位若与 VWAP、MA3/MA5/MA10/MA20、前高前低、成交密集区重合，才提高观察价值。
- 顶部锚点冲不过、放量不涨、留下上影线，按隐藏卖盘和止盈观察处理。
- 底部锚点不能直接当买点；只有缩量止跌、站回 VWAP、完成 09:50-10:10 确认、板块不继续走弱，才允许观察或小仓试错。
- 锚点被放量吃掉，回踩不破，才说明压力被消化，恢复候选资格；恢复候选不等于自动恢复主买资格。
- 高潮后反包优先按先手兑现窗口看，除非放量吃掉压力并回踩不破，不能默认新一轮主升。
```

In `wiki/交易思想/极度看好参与时机.md`, under `common_selection_check` field contract or in the sniper order section, add:

```markdown
- `common_selection_factors`：共同选择拆解。必须同时看昨日持筹者、明日新买盘、主线资金、量化动量四方反应；对子数、整数位和前高前低只作为心理价位与量化锚点辅助，不替代承接修复。
```

Also add a short rule:

```markdown
共同选择一致性要回答四方问题：昨日持筹者为什么不急卖或会在哪里兑现，明日新买盘为什么愿意接，主线资金为什么仍选择这个方向，量化动量看到当前图形是更可能助攻还是反向卖出。
```

- [ ] **Step 4: Update compact context**

In `scripts/knowledge/llm_wiki_context.py`, add four strings to `FIELD_MAPPINGS`:

```python
"心理价位与量化锚点 -> 对子数、整数位、前高前低、VWAP、MA和成交密集区只作价格锚点，不作独立买入理由",
"隐藏买卖盘 -> 顶部锚点冲不过按隐藏卖盘和止盈观察，底部锚点必须站回VWAP并完成10点确认才允许试错",
"量化共同选择 -> 昨日持筹者、明日新买盘、主线资金、量化动量四方一致后才提高参与质量",
"高潮反包 -> 高潮后反包优先按先手兑现点，放量吃掉压力并回踩不破才恢复候选",
```

Append compact digest fragments to `REPORT_DIGEST_TEXT`, keeping length under 700:

```python
"对子数整数位只作价格锚点顶部冲不过先止盈底部站回VWAP和10点确认才试错反包先按兑现点"
```

If the digest becomes too long, remove redundant wording from nearby existing digest text without changing meaning.

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context
```

Expected: pass.

## Task 2: Planned Participation Quant Anchor Fields

**Files:**
- Modify: `scripts/selection/candidate_execution_contracts.py`
- Modify: `scripts/report/decision_ledger.py`
- Test: `tests/test_decision_ledger.py`

- [ ] **Step 1: Add failing decision-ledger tests**

In `tests/test_decision_ledger.py`, add a test near the planned participation tests:

```python
def test_planned_participation_preserves_quant_anchor_fields(self):
    snapshot = build_decision_ledger_snapshot(
        trade_date="2026-05-21",
        extreme_conviction_list=[
            {
                "name": "中微公司",
                "code": "688012",
                "sector": "半导体",
                "conviction_reason": "区间顶部冲高",
                "participation_script": {
                    "participation_window": "09:50-10:10",
                    "anchor_zone_role": "区间顶部",
                    "anchor_line_confluence": "533.33对子锚点接近前高与MA5",
                    "hidden_liquidity_read": "隐藏卖盘更强",
                    "anchor_action_plan": "冲不过先止盈，放量吃掉并回踩不破再恢复候选",
                    "common_selection_factors": "持筹者有兑现压力，新买盘需等VWAP确认，主线资金看半导体延续，量化动量冲不过会转弱",
                    "momentum_feedback_plan": "越跌越弱时不低吸，站回VWAP后再看",
                    "reversal_exit_plan": "反包先按先手兑现点，吃掉压力后再观察",
                },
            }
        ],
    )

    plan = snapshot["cases"][0]["planned_participation"]
    self.assertEqual(plan["anchor_zone_role"], "区间顶部")
    self.assertIn("533.33", plan["anchor_line_confluence"])
    self.assertIn("隐藏卖盘", plan["hidden_liquidity_read"])
    self.assertIn("冲不过先止盈", plan["anchor_action_plan"])
    self.assertIn("持筹者", plan["common_selection_factors"])
    self.assertIn("站回VWAP", plan["momentum_feedback_plan"])
    self.assertIn("反包先按先手兑现点", plan["reversal_exit_plan"])
    self.assertEqual(plan["entry_timing"], "ten_confirm")
```

Add a second test for default generation from a candidate:

```python
def test_default_participation_builds_quant_anchor_plan_from_candidate(self):
    snapshot = build_decision_ledger_snapshot(
        trade_date="2026-05-21",
        extreme_conviction_list=[
            {
                "name": "通富微电",
                "code": "002156",
                "sector": "半导体",
                "conviction_reason": "底部承接观察",
                "anchor_zone_role": "区间底部",
                "anchor_line_confluence": "66.88靠近MA5/VWAP与短线箱体下沿",
                "hidden_liquidity_read": "隐藏买盘待确认",
            }
        ],
    )

    plan = snapshot["cases"][0]["planned_participation"]
    self.assertEqual(plan["anchor_zone_role"], "区间底部")
    self.assertIn("66.88", plan["anchor_line_confluence"])
    self.assertIn("站回VWAP", plan["anchor_action_plan"])
    self.assertIn("四方", plan["common_selection_factors"])
    self.assertIn("反包", plan["reversal_exit_plan"])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_decision_ledger.DecisionLedgerTest.test_planned_participation_preserves_quant_anchor_fields tests.test_decision_ledger.DecisionLedgerTest.test_default_participation_builds_quant_anchor_plan_from_candidate
```

Expected: fail because fields are not preserved/defaulted.

- [ ] **Step 3: Add quant anchor builder**

In `scripts/selection/candidate_execution_contracts.py`, add to `__all__`:

```python
"build_quant_anchor_plan",
```

Add function before `build_participation_window_policy`:

```python
def build_quant_anchor_plan(candidate=None):
    candidate = candidate or {}

    def _text(*keys):
        for key in keys:
            value = candidate.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    zone = _text("anchor_zone_role", "quant_anchor_zone", "price_anchor_zone")
    confluence = _text("anchor_line_confluence", "quant_anchor_confluence", "price_anchor_confluence")
    hidden = _text("hidden_liquidity_read", "hidden_liquidity", "quant_hidden_liquidity")
    action = _text("anchor_action_plan", "quant_anchor_action", "price_anchor_action")
    factors = _text("common_selection_factors", "quant_common_selection_factors")
    momentum = _text("momentum_feedback_plan", "quant_momentum_feedback")
    reversal = _text("reversal_exit_plan", "quant_reversal_exit")

    if not zone and not confluence and not hidden and not action and not factors and not momentum and not reversal:
        return {}

    if not action:
        if "顶部" in zone:
            action = "区间顶部锚点冲不过先止盈；放量吃掉并回踩不破，才恢复候选资格"
        elif "底部" in zone:
            action = "区间底部锚点只作承接观察；缩量止跌、站回VWAP并完成09:50-10:10确认后，才允许小仓试错"
        else:
            action = "锚点只作价格反应观察；必须叠加VWAP、MA和承接确认"
    if not factors:
        factors = "共同选择按四方检查：昨日持筹者、明日新买盘、主线资金、量化动量是否一致"
    if not momentum:
        momentum = "量化动量助攻才提高参与质量；越跌越弱时不低吸，站回VWAP后再看"
    if not reversal:
        reversal = "高潮后反包先按先手兑现点；放量吃掉压力并回踩不破后，才恢复候选观察"

    return {
        "anchor_zone_role": zone or "待确认",
        "anchor_line_confluence": confluence or "等待确认VWAP、MA、前高前低或成交密集区共振",
        "hidden_liquidity_read": hidden or "隐藏买卖盘待确认",
        "anchor_action_plan": action,
        "common_selection_factors": factors,
        "momentum_feedback_plan": momentum,
        "reversal_exit_plan": reversal,
    }
```

In `build_participation_window_policy`, before `return policy`, add:

```python
policy.update(build_quant_anchor_plan(candidate))
```

- [ ] **Step 4: Preserve explicit fields in decision ledger normalization**

In `scripts/report/decision_ledger.py`, extend `script` in `_normalize_participation_script`:

```python
"anchor_zone_role": _value("anchor_zone_role", "quant_anchor_zone", "price_anchor_zone"),
"anchor_line_confluence": _value("anchor_line_confluence", "quant_anchor_confluence", "price_anchor_confluence"),
"hidden_liquidity_read": _value("hidden_liquidity_read", "hidden_liquidity", "quant_hidden_liquidity"),
"anchor_action_plan": _value("anchor_action_plan", "quant_anchor_action", "price_anchor_action"),
"common_selection_factors": _value("common_selection_factors", "quant_common_selection_factors"),
"momentum_feedback_plan": _value("momentum_feedback_plan", "quant_momentum_feedback"),
"reversal_exit_plan": _value("reversal_exit_plan", "quant_reversal_exit"),
```

In `_build_planned_participation`, extend the preserve tuple:

```python
"anchor_zone_role",
"anchor_line_confluence",
"hidden_liquidity_read",
"anchor_action_plan",
"common_selection_factors",
"momentum_feedback_plan",
"reversal_exit_plan",
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_decision_ledger.DecisionLedgerTest.test_planned_participation_preserves_quant_anchor_fields tests.test_decision_ledger.DecisionLedgerTest.test_default_participation_builds_quant_anchor_plan_from_candidate
```

Expected: pass.

## Task 3: Daily Report Rendering And Acceptance

**Files:**
- Modify: `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`
- Test: `tests/test_execution_chain_step1_sections.py` or `tests/test_candidate_selection_stage.py`

- [ ] **Step 1: Add failing render test**

Add a test in the existing candidate selection node test file that calls `build_candidate_selection_conviction_list_node` with an `extreme_conviction_list` item:

```python
def test_conviction_list_renders_quant_anchor_action_plan(self):
    context = {
        "extreme_conviction_list": [
            {
                "name": "中微公司",
                "code": "688012",
                "sector": "半导体",
                "sniper_role": "明日主买对象",
                "leader_speed_tier": "大容量趋势龙头",
                "buy_ma_line": "MA10",
                "sell_ma_line": "MA20",
                "acceptance_repair_required": "缩量回撤到MA10附近，站回VWAP",
                "final_risk_review": {"status": "通过"},
                "conviction_reason": "区间顶部冲高",
                "conviction_rule": "只看承接确认",
                "participation_script": {
                    "participation_window": "09:50-10:10",
                    "anchor_zone_role": "区间顶部",
                    "anchor_line_confluence": "533.33对子锚点接近前高与MA5",
                    "hidden_liquidity_read": "隐藏卖盘更强",
                    "anchor_action_plan": "冲不过先止盈，放量吃掉并回踩不破再恢复候选",
                },
            }
        ]
    }

    lines = build_candidate_selection_conviction_list_node(context)["lines"]
    rendered = "\n".join(lines)
    self.assertIn("量化锚点动作", rendered)
    self.assertIn("533.33对子锚点接近前高与MA5", rendered)
    self.assertIn("冲不过先止盈", rendered)
```

- [ ] **Step 2: Run test to verify failure**

Run the specific test with Python 3.14.

Expected: fail because the table does not render quant-anchor action text.

- [ ] **Step 3: Add formatting helper and table column**

In `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`, add helper:

```python
def _format_quant_anchor_action(script):
    script = script or {}
    confluence = _clean_cell(script.get("anchor_line_confluence"))
    action = _clean_cell(script.get("anchor_action_plan"))
    hidden = _clean_cell(script.get("hidden_liquidity_read"))
    parts = []
    if confluence:
        parts.append(confluence)
    if hidden:
        parts.append(hidden)
    if action:
        parts.append(action)
    if not parts:
        return "-"
    return "量化锚点动作：" + "；".join(parts)
```

Update the participation script table header:

```python
lines.append("| 参与窗口 | 仓位三态 | 涨停惯性 | 盈亏比 | 检查步骤 | 加工依据 | 量化锚点动作 | 集合竞价 | 开盘前几分钟 | 均线回归试错 | 打板策略 | 回封参与 | 错过后动作 | MA20作废 | 跟踪周期 | 作废条件 |")
lines.append("|----------|----------|----------|--------|----------|----------|--------------|----------|--------------|--------------|----------|----------|------------|----------|----------|----------|")
```

Update row construction to insert:

```python
f"{_format_quant_anchor_action(script)} | "
```

between participation basis and auction script.

- [ ] **Step 4: Ensure `_build_participation_script` returns the new fields**

In the same file, inside `_build_participation_script`, make sure returned `script` includes:

```python
"anchor_zone_role": _script_value("anchor_zone_role", default=""),
"anchor_line_confluence": _script_value("anchor_line_confluence", default=""),
"hidden_liquidity_read": _script_value("hidden_liquidity_read", default=""),
"anchor_action_plan": _script_value("anchor_action_plan", default=""),
"common_selection_factors": _script_value("common_selection_factors", default=""),
"momentum_feedback_plan": _script_value("momentum_feedback_plan", default=""),
"reversal_exit_plan": _script_value("reversal_exit_plan", default=""),
```

- [ ] **Step 5: Run render test to verify pass**

Run the specific render test with Python 3.14.

Expected: pass.

## Task 4: Focused Regression

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_decision_ledger tests.test_execution_chain_step1_sections
```

Expected: pass. If the render test lives in another file, include that file instead of or in addition to `tests.test_execution_chain_step1_sections`.

- [ ] **Step 2: Run formatting check**

Run:

```bash
git diff --check -- wiki/交易思想/价格行为与能量框架.md wiki/交易思想/极度看好参与时机.md scripts/knowledge/llm_wiki_context.py scripts/selection/candidate_execution_contracts.py scripts/report/decision_ledger.py scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py tests/test_llm_wiki_context.py tests/test_decision_ledger.py tests/test_execution_chain_step1_sections.py
```

Expected: no output.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git diff -- wiki/交易思想/价格行为与能量框架.md wiki/交易思想/极度看好参与时机.md scripts/knowledge/llm_wiki_context.py scripts/selection/candidate_execution_contracts.py scripts/report/decision_ledger.py scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py tests/test_llm_wiki_context.py tests/test_decision_ledger.py tests/test_execution_chain_step1_sections.py
```

Expected: changes are limited to the quant-anchor design and tests.
