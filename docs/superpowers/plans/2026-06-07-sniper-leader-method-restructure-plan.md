# 狙击手视角龙头战法重构实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 让“明日标的”先从主线、板块锚、总龙、分支龙头和容量中军反推，涨停、连板和明日预期强度只作为后置证据。

**实现思路：** 先用单测锁住“涨停不能直接变主买”和“推导层必须是 4 段动作链”。再最小修改选择逻辑、推导层渲染和候选呈现，最后用 2026-06-05 replay 验证读感和输出顺序。

**技术栈：** Python 3.14、`unittest`、现有 `scripts/selection`、`scripts/report`、`scripts/domains/execution_chain`。

---

## 文件结构

- 修改：`scripts/selection/trend_snapshot_runtime.py`
  - 责任：保证明日主买/补位对象来自板块锚反推，不能因为涨停或连板自动升级。
- 修改：`scripts/report/two_layer_decision_payload.py`
  - 责任：把“推导审计层”从旧 Step 0-5 改为 4 段动作链。
- 修改：`scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`
  - 责任：把重点观察名单的用户可见主表改为“身份关系优先、速度证据后置”的表达。
- 修改：`tests/test_selection_trend_runtime.py`
  - 责任：验证涨停/连板不能替代板块锚，板块锚优先于高分涨停样本。
- 修改：`tests/test_two_layer_decision_payload.py`
  - 责任：验证推导层只渲染新的 4 段动作链。
- 修改：`tests/test_candidate_selection_stage.py`
  - 责任：验证重点观察名单先展示板块锚身份，不把涨停惯性放在身份之前。
- 只读验证：`reports/replay/2026-06-05_A股日报_完整版_replay.md`
  - 责任：用 replay 输出检查最终读感。

所有 Python 命令必须使用：

```bash
.generated/venv-py314/bin/python3.14
```

---

### 任务 1：锁住“涨停不能直接变主买”

**文件：**
- 修改：`tests/test_selection_trend_runtime.py`
- 修改：`scripts/selection/trend_snapshot_runtime.py`

- [ ] **步骤 1：先写失败测试，验证无板块锚的涨停样本只能观察**

在 `tests/test_selection_trend_runtime.py` 的 `build_extreme_conviction_list` 相关测试区追加：

```python
    def test_limit_up_without_anchor_reversal_stays_observation(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "600403",
                    "name": "大有能源",
                    "sector": "煤炭",
                    "tomorrow_strength": 140,
                    "score": 140,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "连板强势",
                    "pattern": "T字板",
                }
            ],
            mainline_name="半导体",
            sector_snapshot=[],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertEqual(len(conviction), 1)
        item = conviction[0]
        self.assertEqual(item["sniper_role"], "候选观察")
        self.assertFalse(item["primary_buy_candidate"])
        self.assertFalse(item["backup_buy_candidate"])
        self.assertEqual(item["candidate_layer"], "watch_sample")
        self.assertIn("观察", item["leader_speed_tier"])
        self.assertIn("涨停", item["ma_role_reason"])
```

- [ ] **步骤 2：写失败测试，验证板块锚优先于更高分涨停样本**

继续在同一测试文件追加：

```python
    def test_anchor_candidate_beats_higher_score_limit_up_sample(self):
        conviction = build_extreme_conviction_list(
            evaluated_stocks=[
                {
                    "code": "603986",
                    "name": "兆易创新",
                    "sector": "半导体",
                    "tomorrow_strength": 82,
                    "score": 82,
                    "change_pct": 4.8,
                    "连板数": 0,
                    "reason": "板块锚定龙，容量中军",
                    "pattern": "趋势承接",
                    "allow_extreme_conviction": True,
                },
                {
                    "code": "600403",
                    "name": "大有能源",
                    "sector": "煤炭",
                    "tomorrow_strength": 140,
                    "score": 140,
                    "change_pct": 10.0,
                    "连板数": 2,
                    "reason": "连板强势",
                    "pattern": "T字板",
                },
            ],
            mainline_name="半导体",
            sector_snapshot=[{"sector": "半导体", "anchor_code": "603986", "density_score": 90}],
            helpers={
                "normalize_stock_code": lambda code: str(code or ""),
                "sector_name_matches": lambda sector, mainline: sector == mainline,
                "_safe_float": lambda value, default=0.0: float(value or default),
            },
        )

        self.assertGreaterEqual(len(conviction), 2)
        self.assertEqual(conviction[0]["code"], "603986")
        self.assertEqual(conviction[0]["sniper_role"], "明日主买对象")
        limit_sample = next(item for item in conviction if item["code"] == "600403")
        self.assertEqual(limit_sample["sniper_role"], "候选观察")
        self.assertFalse(limit_sample["primary_buy_candidate"])
```

- [ ] **步骤 3：运行测试，确认当前实现失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_limit_up_without_anchor_reversal_stays_observation tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_anchor_candidate_beats_higher_score_limit_up_sample
```

预期：至少一个断言失败，失败点应显示涨停样本被升级为主买/补位，或高分涨停排在板块锚之前。

- [ ] **步骤 4：修改角色分配，禁止无锚涨停自动升级**

在 `scripts/selection/trend_snapshot_runtime.py` 中修改 `_assign_sniper_roles`。核心替换逻辑如下：

```python
def _assign_sniper_roles(conviction_list):
    has_anchor_contract = any(
        str((item or {}).get("anchor_reversal_decision") or (item or {}).get("sector_anchor") or "").strip()
        for item in conviction_list or []
    )
    if not has_anchor_contract:
        for item in conviction_list or []:
            item["sniper_role"] = "候选观察"
            item["primary_buy_candidate"] = False
            item["backup_buy_candidate"] = False
            item["candidate_layer"] = "watch_sample"
            item["execution_eligibility"] = "anchor_reversal_required"
            item["attack_state"] = "0%"
            item["participation_window"] = "no_trade"
            item["conviction_rule"] = "未完成板块锚反推，只观察承接，不新增参与"
        return conviction_list

    primary_assigned = False
    backup_assigned = False
    for item in conviction_list or []:
        anchor_decision = str((item or {}).get("anchor_reversal_decision") or "").strip()
        role = "候选观察"
        if anchor_decision == "可作为主对象" and not primary_assigned:
            role = "明日主买对象"
            primary_assigned = True
        elif anchor_decision in {"可作为主对象", "可作为补位"} and not backup_assigned:
            role = "明日补位对象"
            backup_assigned = True
        item["sniper_role"] = role
        item["primary_buy_candidate"] = role == "明日主买对象"
        item["backup_buy_candidate"] = role == "明日补位对象"
        if role == "候选观察" and not str(item.get("anchor_reversal_decision") or "").strip():
            item["candidate_layer"] = "watch_sample"
            item["execution_eligibility"] = "anchor_reversal_required"
            item["attack_state"] = "0%"
            item["participation_window"] = "no_trade"
    return conviction_list
```

- [ ] **步骤 5：修改候选分层，涨停不再绕过板块锚**

在 `_build_extreme_conviction_list_legacy_body` 中，构造 `candidate` 之前，补一段锚点结果收紧逻辑。放在现有 `anchor_decision == "不参与"` 和 `anchor_decision == "降级观察"` 分支之后：

```python
        elif not anchor_decision:
            if int(lianban or 0) >= 1 or _text_contains_any(pattern, ("涨停", "T字", "一字", "光头")):
                action_rule = "未完成板块锚反推，涨停/连板只作观察证据"
                layer_fields = {
                    "candidate_layer": "watch_sample",
                    "execution_eligibility": "anchor_reversal_required",
                }
                participation_fields["attack_state"] = "0%"
                participation_fields["participation_window"] = "no_trade"
                participation_fields["missed_action"] = "只观察，不新增参与"
                participation_fields["board_script"] = "只观察，不新增参与"
                participation_fields.update(
                    build_participation_window_policy("no_trade", "只观察，不新增参与", candidate=stock)
                )
                leader_speed_profile = _observation_leader_speed_profile(
                    "涨停/T字板只是资金表态证据，未通过板块锚反推前只能作为观察样本"
                )
```

- [ ] **步骤 6：运行任务 1 测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_limit_up_without_anchor_reversal_stays_observation tests.test_selection_trend_runtime.SelectionTrendRuntimeTest.test_anchor_candidate_beats_higher_score_limit_up_sample
```

预期：2 个测试通过。

---

### 任务 2：把推导层改成 4 段动作链

**文件：**
- 修改：`tests/test_two_layer_decision_payload.py`
- 修改：`scripts/report/two_layer_decision_payload.py`

- [ ] **步骤 1：更新推导层测试，锁住新标题和顺序**

在 `tests/test_two_layer_decision_payload.py` 中替换 `test_render_derivation_audit_layer_uses_required_step_template` 的断言主体：

```python
        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("## 推导审计层", text)
        self.assertIn("### Step 1：市场是否值得出手", text)
        self.assertIn("### Step 2：主线与龙头身份是否清楚", text)
        self.assertIn("### Step 3：承接和证据是否撑得住", text)
        self.assertIn("### Step 4：明天只做什么", text)
        self.assertNotIn("### Step 0", text)
        self.assertNotIn("### Step 5", text)
        self.assertNotIn("#### 输入数据", text)
        self.assertNotIn("#### 保留与淘汰", text)
        self.assertIn("#### 结论", text)
        self.assertIn("#### 证据", text)
        self.assertIn("#### 动作", text)
        self.assertLess(text.index("主线与龙头身份是否清楚"), text.index("承接和证据是否撑得住"))
        self.assertIn("豫能控股(001896)", text)
```

- [ ] **步骤 2：新增顺序测试，保证涨停证据不在板块锚前**

在同一测试类追加：

```python
    def test_derivation_layer_places_limit_up_evidence_after_anchor_identity(self):
        payload = build_two_layer_decision_payload(
            target_date="2026-06-05",
            final_target_resolution={
                "watch_target": {"name": "大有能源", "code": "600403", "sector": "煤炭"},
                "capital_priority_decision": {"capital_priority": "wait", "reason": "0%不参与"},
            },
            position_decision={"target_position_pct": 0, "final_action": "0%不参与"},
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "无确认主攻线",
                "step2_bundle": {
                    "crossline_observation_stocks": [
                        {
                            "name": "大有能源",
                            "code": "600403",
                            "sector": "煤炭",
                            "pattern": "涨停",
                            "anchor_reversal_decision": "降级观察",
                            "sector_anchor": "兆易创新(603986)",
                            "candidate_role": "跟风样本",
                            "why_not_anchor": "无法替代板块锚",
                            "limit_up_evidence_role": "涨停只作观察证据",
                        }
                    ]
                },
            },
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertLess(text.index("板块锚"), text.index("涨停"))
        self.assertIn("无法替代板块锚", text)
        self.assertIn("只观察", text)
```

- [ ] **步骤 3：运行测试，确认当前实现失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_render_derivation_audit_layer_uses_required_step_template tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_derivation_layer_places_limit_up_evidence_after_anchor_identity
```

预期：当前实现仍渲染旧 Step 0-5 或旧小标题，测试失败。

- [ ] **步骤 4：重写 `_step_payloads` 为 4 段动作链**

在 `scripts/report/two_layer_decision_payload.py` 中替换 `_step_payloads`。实现时保留函数名和调用点，避免扩大影响。结构示例：

```python
def _step_payloads(target, execution_stage_context, final_object=None):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    final_object = final_object if isinstance(final_object, dict) else {}
    market_state = context.get("market_state_snapshot") if isinstance(context.get("market_state_snapshot"), dict) else {}
    mainline = clean_text(
        context.get("mainline_name")
        or (context.get("mainline_turnover_summary") or {}).get("current_mainline")
        or market_state.get("market_state")
        or "待确认"
    )
    target_label = _stock_label(target)
    candidate_labels = _dedupe_labels(_process_candidates_from_context(context))
    has_target = target_label != "暂无"
    observation_stock = (
        final_object.get("stock")
        if final_object.get("identity") == "观察对象" and isinstance(final_object.get("stock"), dict)
        else {}
    )
    observation_label = _stock_label(observation_stock) if observation_stock else ""
    selected_label = target_label if has_target else observation_label
    candidate_text = "、".join(candidate_labels[:3]) if candidate_labels else "无可用候选"
    market_status = clean_text(market_state.get("market_state"), "待确认")

    return [
        {
            "step": "Step 1",
            "title": "市场是否值得出手",
            "conclusion": "可等窗口参与" if has_target else "不做新仓",
            "evidence": [
                f"市场状态：{market_status}",
                f"主方向：{mainline}",
                "市场不支持出手时，后续候选只保留观察或旧仓处理",
            ],
            "action": "继续筛选主线龙头" if has_target else "不新增参与",
        },
        {
            "step": "Step 2",
            "title": "主线与龙头身份是否清楚",
            "conclusion": f"主方向：{mainline}",
            "evidence": _anchor_identity_evidence(context, selected_label, candidate_text),
            "action": "只保留通过板块锚反推的对象",
        },
        {
            "step": "Step 3",
            "title": "承接和证据是否撑得住",
            "conclusion": f"保留对象：{selected_label}" if selected_label and selected_label != "暂无" else "无保留对象",
            "evidence": _acceptance_evidence(context, selected_label),
            "action": "涨停、连板、T字板只作后置证据",
        },
        {
            "step": "Step 4",
            "title": "明天只做什么",
            "conclusion": "参与" if has_target else "不参与",
            "evidence": _discipline_evidence(context, final_object),
            "action": f"明日动作：{_final_action_text(has_target, selected_label)}",
        },
    ]
```

同一文件内新增 helper，放在 `_step_payloads` 上方：

```python
def _anchor_identity_evidence(context, selected_label, candidate_text):
    bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    rows = []
    for item in list(bundle.get("extreme_conviction_list") or []) + list(bundle.get("crossline_observation_stocks") or []):
        if not isinstance(item, dict):
            continue
        label = _stock_label(item)
        anchor = clean_text(item.get("sector_anchor") or (item.get("anchor_reversal") or {}).get("sector_anchor"))
        role = clean_text(item.get("candidate_role") or (item.get("anchor_reversal") or {}).get("candidate_role"))
        why_not_anchor = clean_text(item.get("why_not_anchor") or (item.get("anchor_reversal") or {}).get("why_not_anchor"))
        if anchor or role or why_not_anchor:
            rows.append("；".join(part for part in [label, f"锚：{anchor}" if anchor else "", f"身份：{role}" if role else "", f"不做锚原因：{why_not_anchor}" if why_not_anchor else ""] if part))
        if len(rows) >= 3:
            break
    if rows:
        return rows
    return [f"候选：{candidate_text}", f"当前保留：{selected_label or '无'}", "无板块锚反推时不生成新增参与"]
```

```python
def _acceptance_evidence(context, selected_label):
    bundle = context.get("step2_bundle") if isinstance(context.get("step2_bundle"), dict) else {}
    rows = []
    for item in list(bundle.get("extreme_conviction_list") or []) + list(bundle.get("crossline_observation_stocks") or []):
        if not isinstance(item, dict):
            continue
        label = _stock_label(item)
        acceptance = clean_text(item.get("acceptance_status") or item.get("acceptance_repair_required"))
        limit_role = clean_text(item.get("limit_up_evidence_role") or item.get("leader_speed_tier"))
        if acceptance or limit_role:
            rows.append("；".join(part for part in [label, acceptance, f"速度证据：{limit_role}" if limit_role else ""] if part))
        if len(rows) >= 3:
            break
    if rows:
        return rows
    return [f"保留对象：{selected_label or '无'}", "承接未确认前只观察", "涨停和连板不能替代承接"]
```

```python
def _discipline_evidence(context, final_object):
    final_object = final_object if isinstance(final_object, dict) else {}
    discipline = clean_text(context.get("discipline_status"))
    if not discipline:
        discipline = "未来叙事只作观察或研究；连续盈利后先复核仓位、窗口、失效线"
    invalidations = final_object.get("failure_conditions") if isinstance(final_object.get("failure_conditions"), list) else []
    invalid_text = "；".join(clean_text(item) for item in invalidations[:2] if clean_text(item))
    return [discipline, invalid_text or "固定窗口和失效线未同时满足时不参与"]
```

```python
def _final_action_text(has_target, selected_label):
    if has_target:
        return f"只在固定窗口条件成立时参与{selected_label}"
    if selected_label and selected_label != "暂无":
        return f"只观察{selected_label}，不新增参与"
    return "空仓等待或只处理旧仓"
```

- [ ] **步骤 5：改 `render_derivation_audit_layer`，删除输入/输出清单式小标题**

把该函数的 step 渲染改成：

```python
def render_derivation_audit_layer(payload):
    payload = payload if isinstance(payload, dict) else {}
    lines = ["## 推导审计层"]
    for step in payload.get("derivation_steps", []) or []:
        if not isinstance(step, dict):
            continue
        lines.extend(
            [
                "",
                f"### {clean_text(step.get('step'))}：{clean_text(step.get('title'))}",
                "#### 结论",
                f"- {clean_text(step.get('conclusion'), '-')}",
                "#### 证据",
            ]
        )
        for item in list(step.get("evidence") or [])[:3]:
            lines.append(f"- {clean_text(item)}")
        lines.extend(["#### 动作", f"- {clean_text(step.get('action'), '观察')}"])
    return lines
```

- [ ] **步骤 6：运行任务 2 测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_render_derivation_audit_layer_uses_required_step_template tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_derivation_layer_places_limit_up_evidence_after_anchor_identity
```

预期：2 个测试通过。

---

### 任务 3：调整重点观察名单呈现，先身份后证据

**文件：**
- 修改：`tests/test_candidate_selection_stage.py`
- 修改：`scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py`

- [ ] **步骤 1：写测试，验证重点观察名单先渲染板块锚身份**

在 `tests/test_candidate_selection_stage.py` 的 `conviction_list` 测试区追加：

```python
    def test_conviction_list_renders_anchor_identity_before_limit_evidence(self):
        result = build_candidate_selection_conviction_list_node(
            {
                "extreme_conviction_list": [
                    {
                        "name": "大有能源",
                        "code": "600403",
                        "sector": "煤炭",
                        "pattern": "涨停",
                        "leader_speed_tier": "观察样本",
                        "anchor_reversal_decision": "降级观察",
                        "sector_anchor": "兆易创新(603986)",
                        "candidate_role": "跟风样本",
                        "relationship_to_anchor": "非同主线锚",
                        "why_not_anchor": "无法替代板块锚",
                        "limit_up_evidence_role": "涨停只作观察证据",
                        "conviction_rule": "只观察承接",
                    }
                ]
            }
        )

        rendered = "\n".join(result["lines"])

        self.assertIn("**龙头资格反推结果**", rendered)
        self.assertIn("大有能源(600403)", rendered)
        self.assertLess(rendered.index("板块锚"), rendered.index("涨停只作观察证据"))
        self.assertIn("无法替代板块锚", rendered)
        self.assertNotIn("明日主买对象", rendered)
```

- [ ] **步骤 2：运行测试，确认当前实现失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_selection_stage.CandidateSelectionStageTest.test_conviction_list_renders_anchor_identity_before_limit_evidence
```

预期：当前标题仍是 `重点观察名单`，或涨停证据混在观察理由里，测试失败。

- [ ] **步骤 3：新增格式化函数，把身份关系从长理由中拆出来**

在 `scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py` 中新增：

```python
def _anchor_identity_summary(stock):
    decision = _anchor_reversal_value(stock, "anchor_reversal_decision", "板块锚反推结论")
    sector_anchor = _anchor_reversal_value(stock, "sector_anchor", "板块锚")
    candidate_role = _anchor_reversal_value(stock, "candidate_role", "候选身份")
    relationship = _anchor_reversal_value(stock, "relationship_to_anchor", "与板块锚关系")
    why_not_anchor = _anchor_reversal_value(stock, "why_not_anchor", "为什么不做板块锚", "为什么不做锚", "为什么不做龙头")
    parts = []
    if decision:
        parts.append(f"结论：{decision}")
    if sector_anchor:
        parts.append(f"板块锚：{sector_anchor}")
    if candidate_role:
        parts.append(f"身份：{candidate_role}")
    if relationship:
        parts.append(f"关系：{relationship}")
    if why_not_anchor:
        parts.append(f"不做锚原因：{why_not_anchor}")
    return _clean_cell("；".join(parts), "未完成板块锚反推")
```

```python
def _speed_evidence_summary(stock):
    limit_up_role = _anchor_reversal_value(stock, "limit_up_evidence_role", "涨停证据角色")
    speed_tier = _clean_cell(stock.get("leader_speed_tier"), "")
    pattern = _clean_cell(stock.get("pattern"), "")
    parts = [part for part in (limit_up_role, speed_tier, pattern) if part and part != "-"]
    return _clean_cell("；".join(parts), "无速度加分")
```

- [ ] **步骤 4：改主表标题和列顺序**

在 `build_candidate_selection_conviction_list_node` 中，把原来的：

```python
lines = ["**重点观察名单**（只保留最心动的少数，每只都绑定固定交易窗口条件）:"]
```

改为：

```python
lines = ["**龙头资格反推结果**（先看板块锚和身份，再看速度证据）:"]
```

把主表头从：

```python
lines.append("| 优先级 | 股票 | 代码 | 所属板块 | 核心身份 | 执行分层 | 观察理由 | 明日原则 |")
lines.append("|--------|------|------|----------|----------|----------|----------|----------|")
```

改为：

```python
lines.append("| 优先级 | 标的 | 所属板块 | 板块锚与身份 | 承接结果 | 速度证据 | 明日原则 |")
lines.append("|--------|------|----------|--------------|----------|----------|----------|")
```

把对应行渲染改为：

```python
        for idx, stock in enumerate(extreme_conviction_list[:3], 1):
            lines.append(
                f"| {idx} | {_format_stock_label(stock)} | {_clean_cell(stock.get('sector'))} | "
                f"{_anchor_identity_summary(stock)} | {_clean_cell(stock.get('acceptance_repair_required'), '等待承接确认')} | "
                f"{_speed_evidence_summary(stock)} | {_clean_cell(stock.get('conviction_rule'))} |"
            )
```

- [ ] **步骤 5：限制主链候选数量，长清单不在主链恢复**

同一函数中，`extreme_conviction_list` 主表只渲染前三个；形态待修复池、龙回头观察池、历史去向仍可保留，但它们不应写成“明日主买对象”。如需展示更多候选，只保留在后续复核脚本表里，且不改变主链前三个的动作结论。

- [ ] **步骤 6：运行任务 3 测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_selection_stage.CandidateSelectionStageTest.test_conviction_list_renders_anchor_identity_before_limit_evidence
```

预期：测试通过。

---

### 任务 4：回归测试和 2026-06-05 replay 验证

**文件：**
- 修改：`tests/test_selection_trend_runtime.py`
- 修改：`tests/test_two_layer_decision_payload.py`
- 修改：`tests/test_candidate_selection_stage.py`
- 生成验证：`reports/replay/2026-06-05_A股日报_完整版_replay.md`
- 生成验证：`reports/replay/2026-06-05_A股日报_完整版_replay.html`

- [ ] **步骤 1：运行窄范围单测**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_selection_trend_runtime \
  tests.test_two_layer_decision_payload \
  tests.test_candidate_selection_stage
```

预期：全部通过。

- [ ] **步骤 2：运行受影响执行链单测**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_execution_stage_runtime \
  tests.test_execution_chain_step1_sections \
  tests.test_entry_plan_stage \
  tests.test_pk_decision_stage
```

预期：全部通过。若旧标题断言失败，只更新与本次 Step 重构直接相关的断言，不改无关测试。

- [ ] **步骤 3：重新生成 2026-06-05 replay 日报**

运行：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

预期：

- 只写 `reports/replay/` 和必要的 replay 输出。
- 不生成日报附属大体积数据文件。
- 不覆盖正式历史日报。

- [ ] **步骤 4：检查 replay Markdown 的关键顺序**

运行：

```bash
rg -n "市场是否值得出手|主线与龙头身份是否清楚|承接和证据是否撑得住|明天只做什么|明日预期强度排序|涨停只作|板块锚" reports/replay/2026-06-05_A股日报_完整版_replay.md
```

预期：

- `市场是否值得出手` 先于 `主线与龙头身份是否清楚`。
- `主线与龙头身份是否清楚` 先于 `承接和证据是否撑得住`。
- `板块锚` 先于涨停证据。
- `明天只做什么` 位于四段动作链最后。

- [ ] **步骤 5：检查 replay 中不再出现旧主链标题**

运行：

```bash
rg -n "Step 0|Step 5|Step 6|Step 1 - 明天观察池|Step 2 - 明日核心标的|输入数据|保留与淘汰" reports/replay/2026-06-05_A股日报_完整版_replay.md || true
```

预期：四段动作链主区域不出现这些旧标题。如果其他历史段落仍有旧词，要确认它们不在“狙击手视角 / 推导层”主链里。

- [ ] **步骤 6：人工读感检查**

打开：

```text
reports/replay/2026-06-05_A股日报_完整版_replay.html
```

检查：

- 狙击手视角主链明显短于旧版。
- `大有能源(600403)`、`泰坦股份(003036)`、`凤凰航运(000520)` 这类涨停/连板样本只作为观察或证据，不作为明日主买对象。
- 如果出现 `兆易创新(603986)` 这类板块锚，必须先说明锚点身份，再说明其他候选为什么不能替代它。
- 最终动作仍是 0% 不参与或只观察，不因为明日加速想象打开新增参与。

- [ ] **步骤 7：最终变更检查**

运行：

```bash
git diff --check
```

预期：无输出。

运行：

```bash
git status --short scripts/selection/trend_snapshot_runtime.py scripts/report/two_layer_decision_payload.py scripts/domains/execution_chain/candidate_selection_nodes/conviction_list.py tests/test_selection_trend_runtime.py tests/test_two_layer_decision_payload.py tests/test_candidate_selection_stage.py reports/replay/2026-06-05_A股日报_完整版_replay.md reports/replay/2026-06-05_A股日报_完整版_replay.html
```

预期：只出现本任务相关文件。若 replay HTML/Markdown 已存在并被更新，保留；不要添加任何附属大体积数据文件。

---

## 计划自检

- Spec 覆盖：4 段动作链、板块锚先于涨停、未来叙事只观察、顺境收紧、2026-06-05 replay 验证均有任务覆盖。
- 占位扫描：本文没有待补实现项；每个任务都有明确文件、代码片段、命令和预期。
- 类型一致性：计划中新增判定字段只作为用户可见组织口径；实现优先复用现有字段，避免为字段而字段。
- 范围控制：不改 HTML 样式，不改 PostgreSQL-first，不新增日报附属数据导出物，不重新采集历史行情。
