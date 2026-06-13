# 反推龙头选股工作流实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 新增 `selection_workflow.v1`，让日报最终对象只从一条“市场 -> 资金 -> 板块 -> 角色 -> 反推龙头 -> 候选对照 -> 执行条件”的工作流链条产生。

**实现思路：** 第一版先做兼容层，不重写所有采集和评分模块。先建立结构化工作流载荷和候选生命周期，再把 `final_target_resolution`、`two_layer_decision_payload`、`sniper_target_derivation`、候选追踪和流程图改为消费同一份结果，最后用 2026-06-04、2026-06-05 replay 验证读感。

**技术栈：** Python 3.14、`unittest`、现有 `scripts/report`、`scripts/selection`、PostgreSQL-first 日报快照。

---

## 文件结构

- 新建：`scripts/report/selection_workflow.py`
  - 责任：构建 `selection_workflow.v1`，包含 N0-N9 节点摘要、候选池、最终动作、候选流水账和一致性结果。
- 新建：`tests/test_selection_workflow.py`
  - 责任：锁住工作流节点顺序、候选生命周期、涨停不能直接升级、仓位只能 0/50/100、最终对象必须来自 N8。
- 修改：`scripts/report/runtime.py`
  - 责任：在日报 runtime 中构建并存储 `selection_workflow`，让两处最终对象解析都消费工作流结果。
- 修改：`scripts/report/two_layer_decision_payload.py`
  - 责任：首页和推导层优先从 `selection_workflow` 取最终对象、节点摘要和候选流水账。
- 修改：`scripts/report/sniper_target_derivation.py`
  - 责任：从“事后汇总候选”改成“解释工作流候选生命周期”；没有 workflow 时保留旧兼容。
- 修改：`scripts/selection/candidate_trace_contracts.py`
  - 责任：候选追踪结构扩展 `first_seen_node`、`entered_reason`、`workflow_path`、`eliminated_at`、`eliminated_reason`。
- 修改：`tests/test_report_runtime.py`
  - 责任：验证 runtime 存储 workflow，且 `final_target_resolution`、`two_layer_decision_payload`、`sniper_target_derivation` 指向同一对象。
- 修改：`tests/test_two_layer_decision_payload.py`
  - 责任：验证推导层展示 N1-N8 节点和候选流水账，0% 时不生成新增参与路径。
- 修改：`tests/test_candidate_trace_contracts.py`
  - 责任：验证候选追踪保存生命周期字段。
- 修改：`tests/test_report_acceptance_audit.py`
  - 责任：增加工作流一致性检查，首页、推导层、流程图对象不一致时失败。
- 可选修改：现有 Mermaid 流程图生成脚本或报告流转图生成脚本
  - 责任：从 `selection_workflow.flowchart_payload` 渲染 Mermaid，不再手写另一套解释。执行前先用 `rg` 定位真实脚本。

所有命令必须使用：

```bash
.generated/venv-py314/bin/python3.14
```

---

### 任务 1：建立 `selection_workflow.v1` 最小结构

**文件：**
- 新建：`scripts/report/selection_workflow.py`
- 新建：`tests/test_selection_workflow.py`

- [ ] **步骤 1：先写失败测试，验证节点顺序和最终对象来自 N8**

新建 `tests/test_selection_workflow.py`：

```python
import unittest

from report.selection_workflow import build_selection_workflow


class SelectionWorkflowTest(unittest.TestCase):
    def test_builds_required_nodes_and_final_source(self):
        workflow = build_selection_workflow(
            target_date="2026-06-04",
            data={"target_date": "2026-06-04"},
            execution_stage_context={
                "market_state_snapshot": {"market_state": "发酵"},
                "mainline_name": "电力",
                "mainline_turnover_summary": {"current_mainline": "电力"},
                "sector_trend_snapshot": [
                    {
                        "sector": "电力",
                        "anchor_name": "豫能控股",
                        "anchor_code": "001896",
                        "anchor_reason": "板块锚，资金更容易反复回看",
                    }
                ],
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "source_pools": ["主线核心"],
                        "anchor_reversal_decision": "可作为主对象",
                        "candidate_role": "板块锚",
                        "sector_anchor": "豫能控股(001896)",
                        "conviction_rule": "固定窗口条件成立才参与",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["schema_version"], "selection_workflow.v1")
        self.assertEqual([node["node_id"] for node in workflow["nodes"]], [f"N{i}" for i in range(10)])
        self.assertEqual(workflow["final"]["source_node"], "N8")
        self.assertEqual(workflow["final"]["execution_object"]["code"], "001896")
        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertEqual(workflow["candidate_pool"][0]["first_seen_node"], "N5")
        self.assertEqual(workflow["candidate_pool"][0]["status"], "最终执行对象")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow.SelectionWorkflowTest.test_builds_required_nodes_and_final_source
```

预期：失败，错误包含 `No module named 'report.selection_workflow'`。

- [ ] **步骤 3：写最小实现**

新建 `scripts/report/selection_workflow.py`：

```python
from __future__ import annotations


SCHEMA_VERSION = "selection_workflow.v1"
NODE_DEFS = [
    ("N0", "数据封装"),
    ("N1", "市场周期判断"),
    ("N2", "资金方向判断"),
    ("N3", "板块关系拆解"),
    ("N4", "板块内角色识别"),
    ("N5", "候选池归一"),
    ("N6", "反推龙头"),
    ("N7", "候选对照淘汰"),
    ("N8", "仓位与执行条件"),
    ("N9", "输出一致性复核"),
]
ALLOWED_POSITIONS = {0, 50, 100}


def clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text if text else default


def normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def stock_payload(value):
    if not isinstance(value, dict):
        return {}
    name = clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    code = normalize_stock_code(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    if not (name or code):
        return {}
    payload = {"name": name, "code": code}
    sector = clean_text(value.get("sector") or value.get("sector_name") or value.get("industry") or value.get("板块"))
    if sector:
        payload["sector"] = sector
    return payload


def stock_key(value):
    payload = stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def stock_label(value):
    payload = stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return list(value) if isinstance(value, list) else []


def _position_pct(position_decision=None):
    position_decision = _as_dict(position_decision)
    try:
        value = str(position_decision.get("target_position_pct") or position_decision.get("position_pct") or 0)
        pct = int(float(value.replace("%", "").strip() or 0))
    except (TypeError, ValueError):
        pct = 0
    if pct >= 100:
        return 100
    if pct >= 50:
        return 50
    return 0


def _node(node_id, name, *, input_refs=None, judgement="", passes_forward=None, cannot_conclude=None, candidate_changes=None, conflicts=None):
    return {
        "node_id": node_id,
        "node_name": name,
        "input_refs": list(input_refs or []),
        "input_summary": [],
        "judgement": clean_text(judgement, "待确认"),
        "passes_forward": passes_forward if isinstance(passes_forward, dict) else {},
        "cannot_conclude": list(cannot_conclude or []),
        "conflicts": list(conflicts or []),
        "candidate_changes": list(candidate_changes or []),
    }


def _candidate_sources(execution_stage_context):
    context = _as_dict(execution_stage_context)
    rows = []
    for key in (
        "extreme_conviction_list",
        "crossline_observation_stocks",
        "candidates",
        "watchlist",
        "core_stocks",
        "secondary_stocks",
    ):
        for item in _as_list(context.get(key)):
            if isinstance(item, dict):
                rows.append((key, item))
    return rows


def _candidate_status(candidate, final_key):
    key = stock_key(candidate)
    if final_key and key == final_key:
        return "最终执行对象"
    decision = clean_text(candidate.get("anchor_reversal_decision") or (_as_dict(candidate.get("anchor_reversal")).get("anchor_reversal_decision")))
    if decision == "不参与":
        return "不参与"
    if decision == "降级观察":
        return "降级观察"
    return "过程候选"


def _entered_reason(source_key, candidate):
    reason = clean_text(
        candidate.get("entered_reason")
        or candidate.get("conviction_reason")
        or candidate.get("reason")
        or candidate.get("conviction_rule")
    )
    if reason:
        return reason
    return f"来自{source_key}"


def _build_candidate_pool(execution_stage_context, final_stock):
    final_key = stock_key(final_stock)
    pool = []
    seen = set()
    for source_key, candidate in _candidate_sources(execution_stage_context):
        key = stock_key(candidate)
        if not key or key in seen:
            continue
        seen.add(key)
        status = _candidate_status(candidate, final_key)
        eliminated_at = "" if status == "最终执行对象" else ("N6" if status in {"降级观察", "不参与"} else "")
        eliminated_reason = "" if status == "最终执行对象" else clean_text(
            candidate.get("anchor_reversal_reason")
            or candidate.get("why_not_anchor")
            or candidate.get("conviction_rule")
            or ("未成为最终执行对象" if status == "过程候选" else status)
        )
        pool.append(
            {
                "stock": stock_payload(candidate),
                "first_seen_node": "N5",
                "source_pools": list(candidate.get("source_pools") or [source_key]),
                "entered_reason": _entered_reason(source_key, candidate),
                "mainline": clean_text(candidate.get("mainline") or _as_dict(execution_stage_context).get("mainline_name")),
                "sector": clean_text(candidate.get("sector") or candidate.get("sector_name")),
                "sector_role": clean_text(candidate.get("candidate_role") or candidate.get("core_identity")),
                "reversal_decision": clean_text(candidate.get("anchor_reversal_decision")),
                "status": status,
                "current_reason": clean_text(candidate.get("conviction_rule") or candidate.get("anchor_reversal_reason")),
                "eliminated_at": eliminated_at,
                "eliminated_reason": eliminated_reason,
                "compared_against": [],
                "workflow_path": ["N5", "N6", "N7", "N8"],
            }
        )
    return pool


def _pick_final_candidate(execution_stage_context, selected_position_candidate=None, position_decision=None):
    pct = _position_pct(position_decision)
    if pct <= 0:
        return {}
    selected = stock_payload(selected_position_candidate)
    if selected:
        return selected
    for _, candidate in _candidate_sources(execution_stage_context):
        decision = clean_text(candidate.get("anchor_reversal_decision"))
        if decision == "可作为主对象":
            return stock_payload(candidate)
    return {}


def build_selection_workflow(
    *,
    target_date="",
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    selected_position_candidate=None,
    position_decision=None,
    final_target_resolution=None,
):
    data = _as_dict(data)
    context = _as_dict(execution_stage_context)
    snapshot = _as_dict(market_research_snapshot)
    target_date = clean_text(target_date or data.get("target_date") or snapshot.get("target_date"))
    final_stock = _pick_final_candidate(
        context,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
    )
    pct = _position_pct(position_decision) if final_stock else 0
    market_state = _as_dict(context.get("market_state_snapshot")).get("market_state") or _as_dict(snapshot.get("market_state_snapshot")).get("market_state")
    mainline = clean_text(
        context.get("mainline_name")
        or _as_dict(context.get("mainline_turnover_summary")).get("current_mainline")
        or _as_dict(snapshot.get("mainline_turnover_summary")).get("current_mainline")
    )
    candidate_pool = _build_candidate_pool(context, final_stock)
    final_label = stock_label(final_stock)
    nodes = [
        _node("N0", "数据封装", judgement=f"事实日期：{target_date or '待确认'}", passes_forward={"target_date": target_date}, cannot_conclude=["不能选股", "不能给仓位"]),
        _node("N1", "市场周期判断", input_refs=["N0"], judgement=clean_text(market_state, "市场状态待确认"), passes_forward={"allowed_position_ceiling": pct}, cannot_conclude=["不能指定个股"]),
        _node("N2", "资金方向判断", input_refs=["N1"], judgement=clean_text(_as_dict(context.get("mainline_turnover_summary")).get("relationship") or mainline, "资金方向待确认"), passes_forward={"primary_fund_direction": mainline}, cannot_conclude=["不能直接指定个股"]),
        _node("N3", "板块关系拆解", input_refs=["N1", "N2"], judgement=mainline or "主线待确认", passes_forward={"primary_mainline": mainline}, cannot_conclude=["不能把板块内任意涨停股升级为龙头"]),
        _node("N4", "板块内角色识别", input_refs=["N3"], judgement="识别板块锚、容量中军、弹性先锋和后排反馈", passes_forward={"sector_roles_ready": bool(context.get("sector_trend_snapshot"))}, cannot_conclude=["不能直接给仓位"]),
        _node("N5", "候选池归一", input_refs=["N4"], judgement=f"归一候选{len(candidate_pool)}只", passes_forward={"candidate_count": len(candidate_pool)}, cannot_conclude=["不能生成明日执行对象"]),
        _node("N6", "反推龙头", input_refs=["N5"], judgement=f"保留对象：{final_label if final_stock else '无'}", passes_forward={"leader_candidate": final_stock}, cannot_conclude=["不能直接给仓位"]),
        _node("N7", "候选对照淘汰", input_refs=["N6"], judgement=f"最终对照：{final_label if final_stock else '无执行对象'}", passes_forward={"kept_candidate": final_stock}, cannot_conclude=["不能新增候选"]),
        _node("N8", "仓位与执行条件", input_refs=["N7"], judgement=f"{pct}%{'条件执行' if pct == 50 else ('核心进攻' if pct == 100 else '不参与')}", passes_forward={"execution_object": final_stock, "position_pct": pct}, cannot_conclude=[]),
        _node("N9", "输出一致性复核", input_refs=["N8"], judgement="所有输出消费同一工作流结果", passes_forward={"consistent": True}, cannot_conclude=["不能重新选股"]),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "target_date": target_date,
        "source_date": clean_text(data.get("source_date") or snapshot.get("source_date") or target_date),
        "nodes": nodes,
        "candidate_pool": candidate_pool,
        "final": {
            "execution_object": final_stock,
            "position_pct": pct,
            "action_text": "50%条件执行，不满足回到0%" if pct == 50 else ("100%核心进攻，条件失败回到0%" if pct == 100 else "0%不参与"),
            "source_node": "N8",
            "trigger_paths": [],
            "failure_conditions": [],
            "fail_action": "0%不参与",
        },
        "flowchart_payload": {
            "nodes": [{"id": node["node_id"], "label": node["node_name"], "judgement": node["judgement"]} for node in nodes],
            "final_label": final_label if final_stock else "无执行对象",
        },
    }


def store_selection_workflow(workflow, *targets):
    if not isinstance(workflow, dict) or not workflow:
        return {}
    stored = dict(workflow)
    for target in targets:
        if isinstance(target, dict):
            target["selection_workflow"] = stored
    return stored
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow.SelectionWorkflowTest.test_builds_required_nodes_and_final_source
```

预期：通过。

---

### 任务 2：锁住“涨停来源不能直接升级”和仓位只能 0/50/100

**文件：**
- 修改：`tests/test_selection_workflow.py`
- 修改：`scripts/report/selection_workflow.py`

- [ ] **步骤 1：写失败测试，验证高分涨停但反推未通过只能观察**

在 `SelectionWorkflowTest` 中追加：

```python
    def test_limit_up_without_reversal_cannot_be_final_object(self):
        workflow = build_selection_workflow(
            target_date="2026-06-05",
            execution_stage_context={
                "market_state_snapshot": {"market_state": "收缩防守"},
                "mainline_name": "半导体",
                "extreme_conviction_list": [
                    {
                        "name": "大有能源",
                        "code": "600403",
                        "sector": "煤炭",
                        "pattern": "涨停",
                        "score": 140,
                        "anchor_reversal_decision": "降级观察",
                        "limit_up_evidence_role": "涨停只作观察证据",
                        "why_not_anchor": "无法替代板块锚",
                    }
                ],
            },
            position_decision={"target_position_pct": 50},
        )

        self.assertEqual(workflow["final"]["position_pct"], 0)
        self.assertEqual(workflow["final"]["execution_object"], {})
        self.assertEqual(workflow["candidate_pool"][0]["status"], "降级观察")
        self.assertEqual(workflow["candidate_pool"][0]["eliminated_at"], "N6")
```

- [ ] **步骤 2：写失败测试，验证仓位输入被归一到 0/50/100**

继续追加：

```python
    def test_position_is_normalized_to_allowed_values(self):
        workflow = build_selection_workflow(
            target_date="2026-06-04",
            execution_stage_context={
                "mainline_name": "电力",
                "extreme_conviction_list": [
                    {
                        "name": "豫能控股",
                        "code": "001896",
                        "sector": "电力",
                        "anchor_reversal_decision": "可作为主对象",
                    }
                ],
            },
            position_decision={"target_position_pct": 70},
        )

        self.assertEqual(workflow["final"]["position_pct"], 50)
        self.assertNotIn("70", workflow["final"]["action_text"])
```

- [ ] **步骤 3：运行测试，确认第一条失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow.SelectionWorkflowTest.test_limit_up_without_reversal_cannot_be_final_object tests.test_selection_workflow.SelectionWorkflowTest.test_position_is_normalized_to_allowed_values
```

预期：第一条失败，因为当前 `_pick_final_candidate` 只看仓位和 selected/主对象，未明确阻止反推失败候选。

- [ ] **步骤 4：修改 `_pick_final_candidate`，只允许主对象成为最终对象**

在 `scripts/report/selection_workflow.py` 中替换 `_pick_final_candidate`：

```python
def _candidate_can_be_final(candidate):
    decision = clean_text(candidate.get("anchor_reversal_decision") or _as_dict(candidate.get("anchor_reversal")).get("anchor_reversal_decision"))
    if decision != "可作为主对象":
        return False
    return bool(stock_payload(candidate))


def _pick_final_candidate(execution_stage_context, selected_position_candidate=None, position_decision=None):
    pct = _position_pct(position_decision)
    if pct <= 0:
        return {}
    if _candidate_can_be_final(selected_position_candidate if isinstance(selected_position_candidate, dict) else {}):
        return stock_payload(selected_position_candidate)
    for _, candidate in _candidate_sources(execution_stage_context):
        if _candidate_can_be_final(candidate):
            return stock_payload(candidate)
    return {}
```

- [ ] **步骤 5：运行任务 2 测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow
```

预期：3 个测试全部通过。

---

### 任务 3：让 runtime 构建并存储工作流

**文件：**
- 修改：`scripts/report/runtime.py`
- 修改：`tests/test_report_runtime.py`

- [ ] **步骤 1：写失败测试，验证 runtime helper 存储 workflow**

在 `tests/test_report_runtime.py` 中追加：

```python
    def test_runtime_stores_selection_workflow_on_all_contexts(self):
        data = {"target_date": "2026-06-04"}
        execution_context = {
            "mainline_name": "电力",
            "extreme_conviction_list": [
                {
                    "name": "豫能控股",
                    "code": "001896",
                    "sector": "电力",
                    "anchor_reversal_decision": "可作为主对象",
                }
            ],
        }
        market_snapshot = {}

        workflow = report_runtime._build_runtime_selection_workflow(
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            selected_position_candidate={},
            position_decision={"target_position_pct": 50},
            final_target_resolution={},
        )
        stored = report_runtime._store_runtime_selection_workflow(
            workflow,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )

        self.assertEqual(stored["schema_version"], "selection_workflow.v1")
        self.assertEqual(data["selection_workflow"]["final"]["execution_object"]["code"], "001896")
        self.assertEqual(execution_context["selection_workflow"]["final"]["source_node"], "N8")
        self.assertEqual(market_snapshot["selection_workflow"]["final"]["position_pct"], 50)
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_stores_selection_workflow_on_all_contexts
```

预期：失败，错误包含 `_build_runtime_selection_workflow` 不存在。

- [ ] **步骤 3：在 runtime 导入并添加 helper**

在 `scripts/report/runtime.py` 顶部导入区加入：

```python
from report.selection_workflow import (
    build_selection_workflow as _default_build_selection_workflow,
    store_selection_workflow as _default_store_selection_workflow,
)
```

在 `_build_sniper_target_derivation_packet` 前后新增：

```python
def _build_runtime_selection_workflow(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    selected_position_candidate=None,
    position_decision=None,
    final_target_resolution=None,
):
    builder = globals().get("build_selection_workflow") or _default_build_selection_workflow
    return builder(
        target_date=(data or {}).get("target_date") if isinstance(data, dict) else "",
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_target_resolution=final_target_resolution,
    )


def _store_runtime_selection_workflow(workflow, data=None, execution_stage_context=None, market_research_snapshot=None):
    storer = globals().get("store_selection_workflow") or _default_store_selection_workflow
    stored = storer(workflow, data, execution_stage_context, market_research_snapshot)
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(execution_stage_context, dict) and isinstance(market_research_snapshot, dict):
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
    return stored
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_stores_selection_workflow_on_all_contexts
```

预期：通过。

---

### 任务 4：让 `final_target_resolution` 消费工作流最终结果

**文件：**
- 修改：`scripts/report/runtime.py`
- 修改：`tests/test_report_runtime.py`

- [ ] **步骤 1：写失败测试，验证 workflow 覆盖旧候选**

在 `tests/test_report_runtime.py` 中追加：

```python
    def test_final_target_resolution_uses_selection_workflow_final_object(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "position_pct": 50,
                "action_text": "50%条件执行，不满足回到0%",
                "source_node": "N8",
            },
        }

        resolution = report_runtime._build_runtime_final_target_resolution(
            data={"selection_workflow": workflow},
            selected_position_candidate={"name": "上海石化", "code": "600688", "sector": "石化"},
            position_decision={"target_position_pct": 50},
            market_research_snapshot={},
        )

        self.assertEqual(resolution["new_entry_target"]["code"], "001896")
        self.assertEqual(resolution["process_target"]["code"], "001896")
        self.assertEqual(resolution["capital_priority_decision"]["capital_priority"], "new_entry")
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_uses_selection_workflow_final_object
```

预期：失败，当前函数仍使用 `selected_position_candidate`。

- [ ] **步骤 3：新增 workflow final 提取 helper**

在 `scripts/report/runtime.py` 的 `_build_runtime_final_target_resolution` 前新增：

```python
def _runtime_selection_workflow_final(data=None, market_research_snapshot=None, execution_stage_context=None):
    for source in (data, market_research_snapshot, execution_stage_context):
        workflow = source.get("selection_workflow") if isinstance(source, dict) else {}
        if not isinstance(workflow, dict):
            continue
        final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
        target = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
        if _runtime_candidate_key(target):
            return final
    return {}
```

- [ ] **步骤 4：修改 `_build_runtime_final_target_resolution` 开头**

在 `_build_runtime_final_target_resolution` 中，进入旧逻辑前加入：

```python
    workflow_final = _runtime_selection_workflow_final(data=data, market_research_snapshot=market_research_snapshot)
    if workflow_final:
        selected_position_candidate = dict(workflow_final.get("execution_object") or {})
        position_decision = dict(position_decision or {})
        position_decision["target_position_pct"] = workflow_final.get("position_pct", position_decision.get("target_position_pct", 0))
```

这样保留旧账户和代理标的逻辑，但候选对象来自 workflow。

- [ ] **步骤 5：运行任务 4 测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_uses_selection_workflow_final_object
```

预期：通过。

---

### 任务 5：在主 runtime 两个解析点接入工作流

**文件：**
- 修改：`scripts/report/runtime.py`
- 修改：`tests/test_report_runtime.py`

- [ ] **步骤 1：写测试，验证主流程构造顺序**

在 `tests/test_report_runtime.py` 中追加一个不跑全日报的 helper 级测试：

```python
    def test_selection_workflow_can_feed_two_layer_and_sniper_packets(self):
        data = {"target_date": "2026-06-04"}
        execution_context = {
            "mainline_name": "电力",
            "extreme_conviction_list": [
                {"name": "豫能控股", "code": "001896", "sector": "电力", "anchor_reversal_decision": "可作为主对象"}
            ],
        }
        market_snapshot = {}
        position_decision = {"target_position_pct": 50}

        workflow = report_runtime._build_runtime_selection_workflow(
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
            selected_position_candidate={},
            position_decision=position_decision,
            final_target_resolution={},
        )
        report_runtime._store_runtime_selection_workflow(
            workflow,
            data=data,
            execution_stage_context=execution_context,
            market_research_snapshot=market_snapshot,
        )
        resolution = report_runtime._build_runtime_final_target_resolution(
            data=data,
            selected_position_candidate={"name": "上海石化", "code": "600688"},
            position_decision=position_decision,
            market_research_snapshot=market_snapshot,
        )

        self.assertEqual(resolution["new_entry_target"]["code"], "001896")
```

- [ ] **步骤 2：运行测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_can_feed_two_layer_and_sniper_packets
```

预期：通过。如果失败，先修任务 3 或任务 4 的 helper。

- [ ] **步骤 3：在 runtime 第一次 final resolution 前接入 workflow**

在 `scripts/report/runtime.py` 第一次调用 `_build_runtime_final_target_resolution` 前，也就是 `position_decision = _build_front_page_position_decision(...)` 之后、`final_target_resolution = _build_runtime_final_target_resolution(...)` 之前，加入：

```python
    selection_workflow = _build_runtime_selection_workflow(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_target_resolution={},
    )
    _store_runtime_selection_workflow(
        selection_workflow,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
```

- [ ] **步骤 4：在 runtime 第二次 final resolution 前刷新 workflow**

在文件尾部第二次调用 `_build_runtime_final_target_resolution` 前，也就是第二次 `position_decision = _build_front_page_position_decision(...)` 之后、第二次 `final_target_resolution = _build_runtime_final_target_resolution(...)` 之前，加入同样逻辑，但传入现有 `final_target_resolution`：

```python
    selection_workflow = _build_runtime_selection_workflow(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        selected_position_candidate=selected_position_candidate,
        position_decision=position_decision,
        final_target_resolution=final_target_resolution,
    )
    _store_runtime_selection_workflow(
        selection_workflow,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
```

- [ ] **步骤 5：运行受影响 runtime 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime.ReportRuntimeTest.test_runtime_stores_selection_workflow_on_all_contexts \
  tests.test_report_runtime.ReportRuntimeTest.test_final_target_resolution_uses_selection_workflow_final_object \
  tests.test_report_runtime.ReportRuntimeTest.test_selection_workflow_can_feed_two_layer_and_sniper_packets
```

预期：全部通过。

---

### 任务 6：让双层决策载荷消费工作流

**文件：**
- 修改：`scripts/report/two_layer_decision_payload.py`
- 修改：`tests/test_two_layer_decision_payload.py`

- [ ] **步骤 1：写失败测试，验证 front decision 来自 workflow**

在 `tests/test_two_layer_decision_payload.py` 追加：

```python
    def test_front_decision_uses_selection_workflow_final_object(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896", "sector": "电力"},
                "position_pct": 50,
                "action_text": "50%条件执行，不满足回到0%",
                "source_node": "N8",
            },
            "nodes": [{"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "50%条件执行"}],
            "candidate_pool": [],
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={
                "display_target": {"name": "上海石化", "code": "600688"},
                "capital_priority_decision": {"capital_priority": "new_entry"},
            },
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        self.assertEqual(payload["front_decision"]["execution_object"]["code"], "001896")
        self.assertEqual(payload["front_decision"]["position_plan"], "50%条件执行")
```

- [ ] **步骤 2：写失败测试，验证推导层展示 workflow 节点和候选流水账**

继续追加：

```python
    def test_derivation_layer_renders_selection_workflow_nodes_and_candidate_pool(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "nodes": [
                {"node_id": "N1", "node_name": "市场周期判断", "judgement": "允许继续诊断", "passes_forward": {"x": "y"}, "cannot_conclude": ["不能指定个股"]},
                {"node_id": "N6", "node_name": "反推龙头", "judgement": "保留豫能控股", "passes_forward": {}, "cannot_conclude": ["不能直接给仓位"]},
                {"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "50%条件执行", "passes_forward": {}, "cannot_conclude": []},
            ],
            "candidate_pool": [
                {
                    "stock": {"name": "豫能控股", "code": "001896"},
                    "source_pools": ["主线核心"],
                    "entered_reason": "电力窗口方向",
                    "sector_role": "板块锚",
                    "reversal_decision": "可作为主对象",
                    "status": "最终执行对象",
                    "eliminated_reason": "",
                },
                {
                    "stock": {"name": "上海石化", "code": "600688"},
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "sector_role": "过程候选",
                    "reversal_decision": "降级观察",
                    "status": "降级观察",
                    "eliminated_reason": "不是当前主线核心",
                },
            ],
            "final": {"execution_object": {"name": "豫能控股", "code": "001896"}, "position_pct": 50},
        }
        payload = build_two_layer_decision_payload(
            target_date="2026-06-04",
            final_target_resolution={},
            position_decision={"target_position_pct": 50},
            execution_stage_context={"selection_workflow": workflow},
        )

        text = "\n".join(render_derivation_audit_layer(payload))

        self.assertIn("N1 市场周期判断", text)
        self.assertIn("N6 反推龙头", text)
        self.assertIn("候选流水账", text)
        self.assertIn("豫能控股(001896)", text)
        self.assertIn("上海石化(600688)", text)
        self.assertLess(text.index("N1 市场周期判断"), text.index("N6 反推龙头"))
```

- [ ] **步骤 3：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_front_decision_uses_selection_workflow_final_object \
  tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_derivation_layer_renders_selection_workflow_nodes_and_candidate_pool
```

预期：失败，当前 `build_two_layer_decision_payload` 不消费 workflow。

- [ ] **步骤 4：新增 workflow 提取 helper**

在 `scripts/report/two_layer_decision_payload.py` 中新增：

```python
def _selection_workflow_from_context(execution_stage_context):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    workflow = context.get("selection_workflow")
    if isinstance(workflow, dict):
        return workflow
    snapshot = context.get("market_research_snapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("selection_workflow"), dict):
        return snapshot.get("selection_workflow")
    return {}
```

新增：

```python
def _workflow_final_target(workflow):
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    target = final.get("execution_object") if isinstance(final.get("execution_object"), dict) else {}
    return target if _stock_key(target) else {}
```

如果文件没有 `_stock_key`，新增：

```python
def _stock_key(value):
    payload = _stock_payload(value)
    return payload.get("code") or payload.get("name") or ""
```

- [ ] **步骤 5：修改 `build_two_layer_decision_payload` 入口**

在函数开头获取 workflow：

```python
    workflow = _selection_workflow_from_context(execution_stage_context)
```

在构建 `front_decision` 前，如果 `workflow` 有 final target，则覆盖用于前台的对象和仓位：

```python
    workflow_target = _workflow_final_target(workflow)
    workflow_final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
```

把 `front_decision` 的 `execution_object` 和 `position_plan` 改为优先用 workflow：

```python
    if workflow_target:
        front_decision["execution_object"] = _stock_payload(workflow_target)
        front_decision["execution_identity"] = "明日执行对象"
        pct = int(workflow_final.get("position_pct") or 0)
        front_decision["position_plan"] = "100%核心进攻" if pct >= 100 else ("50%条件执行" if pct >= 50 else "0%不参与")
```

并在 payload 中加入：

```python
        "selection_workflow": workflow,
```

- [ ] **步骤 6：修改 `render_derivation_audit_layer` 优先渲染 workflow**

在函数开头加入：

```python
    workflow = payload.get("selection_workflow") if isinstance(payload.get("selection_workflow"), dict) else {}
    if workflow:
        return render_selection_workflow_derivation_layer(workflow)
```

新增：

```python
def render_selection_workflow_derivation_layer(workflow):
    lines = ["## 推导审计层", "", "### 工作流链条"]
    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = clean_text(node.get("node_id"))
        node_name = clean_text(node.get("node_name"))
        lines.extend(
            [
                "",
                f"#### {node_id} {node_name}",
                f"- 结论：{clean_text(node.get('judgement'), '待确认')}",
                f"- 传给下一步：{clean_text(node.get('passes_forward'), '{}')}",
                f"- 本节点不能推出：{'；'.join(node.get('cannot_conclude') or []) or '无'}",
            ]
        )
    lines.extend(["", "### 候选流水账"])
    lines.append("| 股票 | 首次来源 | 进入理由 | 板块角色 | 反推结论 | 对照结果 | 最终动作 |")
    lines.append("|---|---|---|---|---|---|---|")
    for item in workflow.get("candidate_pool", []) or []:
        if not isinstance(item, dict):
            continue
        stock = item.get("stock") if isinstance(item.get("stock"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    _stock_label(stock),
                    "、".join(item.get("source_pools") or []) or "-",
                    clean_text(item.get("entered_reason"), "-"),
                    clean_text(item.get("sector_role"), "-"),
                    clean_text(item.get("reversal_decision"), "-"),
                    clean_text(item.get("eliminated_reason"), clean_text(item.get("status"), "-")),
                    clean_text(item.get("status"), "-"),
                ]
            )
            + " |"
        )
    return lines
```

- [ ] **步骤 7：运行任务 6 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_front_decision_uses_selection_workflow_final_object \
  tests.test_two_layer_decision_payload.TwoLayerDecisionPayloadTest.test_derivation_layer_renders_selection_workflow_nodes_and_candidate_pool
```

预期：通过。

---

### 任务 7：让狙击手推导解释工作流候选生命周期

**文件：**
- 修改：`scripts/report/sniper_target_derivation.py`
- 修改：`tests/test_report_runtime.py`

- [ ] **步骤 1：写失败测试，验证 packet 使用 workflow candidate_pool**

在 `tests/test_report_runtime.py` 中追加：

```python
    def test_sniper_target_derivation_uses_selection_workflow_candidate_pool(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "candidate_pool": [
                {
                    "stock": {"name": "豫能控股", "code": "001896"},
                    "source_pools": ["主线核心"],
                    "entered_reason": "电力窗口方向",
                    "status": "最终执行对象",
                    "current_reason": "对照胜出",
                },
                {
                    "stock": {"name": "上海石化", "code": "600688"},
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "status": "降级观察",
                    "eliminated_reason": "不是当前主线核心",
                },
            ],
            "final": {
                "execution_object": {"name": "豫能控股", "code": "001896"},
                "position_pct": 50,
                "action_text": "50%条件执行，不满足回到0%",
            },
        }
        packet = report_runtime._build_sniper_target_derivation_packet(
            data={"target_date": "2026-06-04", "selection_workflow": workflow},
            execution_stage_context={"selection_workflow": workflow},
            market_research_snapshot={},
            final_target_resolution={},
            selected_position_candidate={},
            position_decision={"target_position_pct": 50},
            two_layer_decision_payload={},
        )

        self.assertEqual(packet["canonical_target"]["code"], "001896")
        step_text = "\n".join(step["reason"] for step in packet["steps"])
        self.assertIn("电力窗口方向", step_text)
        self.assertIn("不是当前主线核心", step_text)
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_sniper_target_derivation_uses_selection_workflow_candidate_pool
```

预期：失败，当前 packet 不识别 workflow。

- [ ] **步骤 3：在 `sniper_target_derivation.py` 新增 workflow packet 构建**

新增：

```python
def _selection_workflow_from_sources(*sources):
    for source in sources:
        workflow = source.get("selection_workflow") if isinstance(source, dict) else {}
        if isinstance(workflow, dict) and workflow.get("schema_version") == "selection_workflow.v1":
            return workflow
    return {}


def _packet_from_selection_workflow(workflow, target_date=""):
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    canonical = stock_payload(final.get("execution_object"))
    canonical_role = "执行对象" if canonical and int(final.get("position_pct") or 0) > 0 else "观察对象"
    if canonical:
        canonical["role"] = canonical_role
    steps = []
    for index, item in enumerate(workflow.get("candidate_pool") or [], start=1):
        if not isinstance(item, dict):
            continue
        stock = stock_payload(item.get("stock"))
        if not stock:
            continue
        same = bool(stock_key(stock) and stock_key(stock) == stock_key(canonical))
        _append_step(
            steps,
            step_id="N5-N8",
            label="工作流候选生命周期",
            source="selection_workflow.candidate_pool",
            candidate=stock,
            role=item.get("status") or ("最终执行对象" if same else "过程候选"),
            decision="保留" if same else "被淘汰",
            reason=clean_text(item.get("current_reason") or item.get("eliminated_reason") or item.get("entered_reason")),
            source_rank=index,
        )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "target_date": clean_text(target_date or workflow.get("target_date")),
        "canonical_target": canonical,
        "canonical_source": "selection_workflow.final.execution_object",
        "canonical_role": canonical_role,
        "final_action": {
            "position_pct": int(final.get("position_pct") or 0),
            "action": clean_text(final.get("action_text"), "0%不参与"),
            "reason": "来自 selection_workflow.v1 的 N8 仓位与执行条件",
        },
        "steps": steps,
        "warnings": [],
    }
    packet["compact_ascii"] = render_compact_ascii(packet)
    packet["full_ascii"] = render_full_ascii(packet)
    return packet
```

- [ ] **步骤 4：修改 `build_sniper_target_derivation_packet` 开头**

在函数清洗 `data/execution_stage_context/market_research_snapshot` 后加入：

```python
    workflow = _selection_workflow_from_sources(data, execution_stage_context, market_research_snapshot)
    if workflow:
        return _packet_from_selection_workflow(
            workflow,
            target_date=target_date or data.get("target_date") or market_research_snapshot.get("target_date"),
        )
```

- [ ] **步骤 5：运行任务 7 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_sniper_target_derivation_uses_selection_workflow_candidate_pool
```

预期：通过。

---

### 任务 8：扩展候选追踪生命周期字段

**文件：**
- 修改：`scripts/selection/candidate_trace_contracts.py`
- 修改：`tests/test_candidate_trace_contracts.py`

- [ ] **步骤 1：写失败测试**

在 `tests/test_candidate_trace_contracts.py` 中追加：

```python
    def test_candidate_trace_preserves_selection_workflow_lifecycle(self):
        trace = build_candidate_trace(
            {
                "name": "上海石化",
                "code": "600688",
                "mainline": "电力",
                "sector": "石化",
                "market_fit": "满足",
                "mainline_fit": "未满足",
                "stock_structure_fit": "部分满足",
                "first_seen_node": "N5",
                "entered_reason": "涨停池样本",
                "workflow_path": ["N5", "N6", "N7"],
                "eliminated_at": "N6",
                "eliminated_reason": "不是当前主线核心",
            }
        )

        self.assertEqual(trace["first_seen_node"], "N5")
        self.assertEqual(trace["entered_reason"], "涨停池样本")
        self.assertEqual(trace["workflow_path"], ["N5", "N6", "N7"])
        self.assertEqual(trace["eliminated_at"], "N6")
        self.assertEqual(trace["eliminated_reason"], "不是当前主线核心")
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_contracts.CandidateTraceContractsTest.test_candidate_trace_preserves_selection_workflow_lifecycle
```

预期：失败，字段不存在。

- [ ] **步骤 3：修改 `build_candidate_trace` 追加字段**

在 `trace = { ... }` 构造后、`if anchor_reversal:` 前加入：

```python
    for key in ("first_seen_node", "entered_reason", "eliminated_at", "eliminated_reason"):
        value = _clean_text(candidate.get(key))
        if value:
            trace[key] = value
    workflow_path = _as_list(candidate.get("workflow_path"))
    if workflow_path:
        trace["workflow_path"] = workflow_path
```

- [ ] **步骤 4：运行任务 8 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_trace_contracts.CandidateTraceContractsTest.test_candidate_trace_preserves_selection_workflow_lifecycle
```

预期：通过。

---

### 任务 9：把 workflow candidate_pool 导出为 candidate traces

**文件：**
- 修改：`scripts/report/runtime.py`
- 修改：`tests/test_report_runtime.py`

- [ ] **步骤 1：写失败测试**

在 `tests/test_report_runtime.py` 中追加：

```python
    def test_runtime_candidate_traces_can_be_built_from_selection_workflow(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "candidate_pool": [
                {
                    "stock": {"name": "上海石化", "code": "600688", "sector": "石化"},
                    "first_seen_node": "N5",
                    "source_pools": ["涨停池"],
                    "entered_reason": "涨停样本",
                    "mainline": "电力",
                    "sector": "石化",
                    "status": "降级观察",
                    "eliminated_at": "N6",
                    "eliminated_reason": "不是当前主线核心",
                }
            ],
        }
        traces = report_runtime._candidate_traces_from_selection_workflow(workflow)

        self.assertEqual(traces[0]["stock_code"], "600688")
        self.assertEqual(traces[0]["first_seen_node"], "N5")
        self.assertEqual(traces[0]["entered_reason"], "涨停样本")
        self.assertEqual(traces[0]["eliminated_at"], "N6")
```

- [ ] **步骤 2：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_candidate_traces_can_be_built_from_selection_workflow
```

预期：失败，helper 不存在。

- [ ] **步骤 3：在 runtime 导入 candidate trace builder**

在 `scripts/report/runtime.py` 导入区加入：

```python
from selection.candidate_trace_contracts import build_candidate_trace as _default_build_candidate_trace
```

- [ ] **步骤 4：新增 `_candidate_traces_from_selection_workflow`**

在 `_maybe_persist_candidate_traces` 前新增：

```python
def _candidate_traces_from_selection_workflow(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    traces = []
    for item in workflow.get("candidate_pool", []) or []:
        if not isinstance(item, dict):
            continue
        stock = item.get("stock") if isinstance(item.get("stock"), dict) else {}
        candidate = {
            **stock,
            "mainline": item.get("mainline"),
            "sector": item.get("sector") or stock.get("sector"),
            "source_pools": item.get("source_pools") or [],
            "market_fit": "满足",
            "mainline_fit": "未满足" if item.get("eliminated_at") == "N6" else "满足",
            "stock_structure_fit": "部分满足" if item.get("status") != "最终执行对象" else "满足",
            "first_seen_node": item.get("first_seen_node"),
            "entered_reason": item.get("entered_reason"),
            "workflow_path": item.get("workflow_path"),
            "eliminated_at": item.get("eliminated_at"),
            "eliminated_reason": item.get("eliminated_reason"),
            "final_action": item.get("status"),
        }
        trace = _default_build_candidate_trace(candidate)
        if trace.get("stock_code") or trace.get("stock_name"):
            traces.append(trace)
    return traces
```

- [ ] **步骤 5：在存储 workflow 后同步 candidate traces**

在 `_store_runtime_selection_workflow` 中，`stored = storer(...)` 之后加入：

```python
    traces = _candidate_traces_from_selection_workflow(stored)
    if traces and isinstance(execution_stage_context, dict):
        execution_stage_context["candidate_traces"] = traces
```

- [ ] **步骤 6：运行任务 9 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_runtime_candidate_traces_can_be_built_from_selection_workflow
```

预期：通过。

---

### 任务 10：增加报告一致性检查

**文件：**
- 修改：`scripts/report/report_acceptance_audit.py`
- 修改：`tests/test_report_acceptance_audit.py`

- [ ] **步骤 1：先定位现有 audit 入口**

运行：

```bash
rg -n "def audit|def .*audit|sniper_target_derivation_mismatch|final_target" scripts/report/report_acceptance_audit.py
```

预期：能看到 `_audit_sniper_target_derivation_consistency` 和总入口。

- [ ] **步骤 2：写失败测试**

在 `tests/test_report_acceptance_audit.py` 中追加：

```python
    def test_audit_flags_selection_workflow_mismatch(self):
        lines = [
            "## 明日诊断结论",
            "| 唯一对象 | 豫能控股(001896) |",
            "## 推导审计层",
            "### 候选流水账",
            "| 上海石化(600688) | 涨停池 | 涨停样本 | 过程候选 | 降级观察 | 被淘汰 | 不参与 |",
            "```json",
            '{"selection_workflow":{"schema_version":"selection_workflow.v1","final":{"execution_object":{"name":"上海石化","code":"600688"},"position_pct":50}}}',
            "```",
        ]

        result = report_acceptance_audit.audit_report_lines(lines)

        self.assertIn("selection_workflow_mismatch", {finding["code"] for finding in result["findings"]})
```

如果测试文件总入口不是 `audit_report_lines`，按步骤 1 的真实函数名替换。

- [ ] **步骤 3：运行测试，确认当前失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_flags_selection_workflow_mismatch
```

预期：失败，未产生 `selection_workflow_mismatch`。

- [ ] **步骤 4：新增最小文本一致性检查**

在 `scripts/report/report_acceptance_audit.py` 中新增：

```python
def _audit_selection_workflow_consistency(lines):
    text = "\n".join(lines or [])
    if "selection_workflow.v1" not in text:
        return []
    findings = []
    workflow_target = ""
    match = re.search(r'"execution_object"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"code"\s*:\s*"([^"]+)"', text)
    if match:
        workflow_target = f"{match.group(1)}({match.group(2)})"
    if workflow_target and "唯一对象" in text and workflow_target not in text.split("## 推导审计层", 1)[0]:
        findings.append(
            {
                "code": "selection_workflow_mismatch",
                "severity": "error",
                "message": f"首页对象与 selection_workflow 最终对象不一致：{workflow_target}",
            }
        )
    return findings
```

确保文件已导入 `re`，没有则加：

```python
import re
```

在总入口追加：

```python
    findings.extend(_audit_selection_workflow_consistency(lines))
```

- [ ] **步骤 5：运行任务 10 测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_flags_selection_workflow_mismatch
```

预期：通过。

---

### 任务 11：让 Mermaid 流程图消费 workflow payload

**文件：**
- 待定位后修改：实际 Mermaid 流程图生成脚本
- 新增或修改：对应测试文件

- [ ] **步骤 1：定位真实流程图生成入口**

运行：

```bash
rg -n "Mermaid|mermaid|flowcharts|流转图|流程图|当前日报选股" scripts tests docs
```

预期：找到生成 `/reports/flowcharts/当前日报选股到最终标的的流转图.html` 的脚本或测试。如果没有入口，先记录为新建脚本。

- [ ] **步骤 2：如果没有现成脚本，新建测试**

新建 `tests/test_selection_workflow_flowchart.py`：

```python
import unittest

from report.selection_workflow import render_selection_workflow_mermaid


class SelectionWorkflowFlowchartTest(unittest.TestCase):
    def test_render_mermaid_from_workflow_nodes(self):
        workflow = {
            "schema_version": "selection_workflow.v1",
            "nodes": [
                {"node_id": "N1", "node_name": "市场周期判断", "judgement": "允许继续诊断"},
                {"node_id": "N3", "node_name": "板块关系拆解", "judgement": "电力成为窗口方向"},
                {"node_id": "N8", "node_name": "仓位与执行条件", "judgement": "50%条件执行"},
            ],
            "final": {"execution_object": {"name": "豫能控股", "code": "001896"}, "position_pct": 50},
        }
        mermaid = render_selection_workflow_mermaid(workflow)

        self.assertIn("flowchart TD", mermaid)
        self.assertIn("N1[\"N1 市场周期判断", mermaid)
        self.assertIn("N8[\"N8 仓位与执行条件", mermaid)
        self.assertIn("豫能控股(001896)", mermaid)
```

- [ ] **步骤 3：运行测试，确认失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow_flowchart
```

预期：失败，`render_selection_workflow_mermaid` 不存在。

- [ ] **步骤 4：在 `selection_workflow.py` 新增 Mermaid 渲染函数**

追加：

```python
def _mermaid_escape(value):
    return clean_text(value).replace('"', "'")


def render_selection_workflow_mermaid(workflow):
    workflow = workflow if isinstance(workflow, dict) else {}
    lines = ["flowchart TD"]
    previous = ""
    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = clean_text(node.get("node_id"))
        label = _mermaid_escape(f"{node_id} {node.get('node_name')}\\n{node.get('judgement')}")
        lines.append(f'  {node_id}["{label}"]')
        if previous:
            lines.append(f"  {previous} --> {node_id}")
        previous = node_id
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    target = stock_label(final.get("execution_object"))
    pct = final.get("position_pct", 0)
    final_label = _mermaid_escape(f"最终：{target}\\n仓位：{pct}%")
    lines.append(f'  FINAL["{final_label}"]')
    if previous:
        lines.append(f"  {previous} --> FINAL")
    return "\\n".join(lines)
```

在 `__all__` 如有则加入函数名；如果没有 `__all__` 不需要加。

- [ ] **步骤 5：运行流程图测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_selection_workflow_flowchart
```

预期：通过。

- [ ] **步骤 6：把真实 HTML 生成改为使用 Mermaid 函数**

按步骤 1 找到的真实脚本，改为从快照或日报数据里的 `selection_workflow` 读取并调用：

```python
from report.selection_workflow import render_selection_workflow_mermaid
```

核心替换：

```python
mermaid_source = render_selection_workflow_mermaid(selection_workflow)
```

如果真实脚本不存在，新建轻量脚本 `scripts/report/selection_workflow_flowchart.py`，负责把 workflow 写成 HTML。不要接入外部服务。

---

### 任务 12：聚焦回归测试

**文件：**
- 所有本计划修改文件

- [ ] **步骤 1：运行新增和核心单测**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_selection_workflow \
  tests.test_selection_workflow_flowchart \
  tests.test_two_layer_decision_payload \
  tests.test_candidate_trace_contracts
```

预期：全部通过。

- [ ] **步骤 2：运行 runtime 和一致性测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_report_runtime \
  tests.test_report_acceptance_audit
```

预期：全部通过。若时间太长或存在无关历史失败，记录失败测试名和是否与本次修改相关。

- [ ] **步骤 3：运行受影响渲染测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_front_page_v2_renderer \
  tests.test_final_conclusion_renderer \
  tests.test_action_plan_renderer
```

预期：全部通过。若旧断言只因新增 workflow 字段或文案顺序变化失败，只更新与本次主链相关的断言。

---

### 任务 13：Replay 验证 2026-06-04 和 2026-06-05

**文件：**
- 生成：`reports/replay/2026-06-04_A股日报_完整版_replay.md`
- 生成：`reports/replay/2026-06-05_A股日报_完整版_replay.md`
- 生成：对应 HTML

- [ ] **步骤 1：重新生成 2026-06-04 replay**

运行：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
```

预期：命令成功，只写 replay 输出，不覆盖正式历史日报。

- [ ] **步骤 2：重新生成 2026-06-05 replay**

运行：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

预期：命令成功，只写 replay 输出，不覆盖正式历史日报。

- [ ] **步骤 3：检查 workflow 关键内容**

运行：

```bash
rg -n "selection_workflow.v1|工作流链条|候选流水账|N1 市场周期判断|N3 板块关系拆解|N6 反推龙头|N8 仓位与执行条件|为什么是它|涨停只作" reports/replay/2026-06-04_A股日报_完整版_replay.md reports/replay/2026-06-05_A股日报_完整版_replay.md
```

预期：

- 两份 replay 都出现工作流链条和候选流水账。
- `N1` 在 `N6` 之前。
- `N6` 在 `N8` 之前。
- 涨停证据出现在反推龙头之后。

- [ ] **步骤 4：检查废弃路径和旧仓位表达没有回流**

运行：

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path

terms = [
    "A" + "档",
    "B" + "档",
    "C" + "档",
    "一" + "档",
    "二" + "档",
    "三" + "档",
    "3" + "0%",
    "小" + "仓试错",
    "snap" + "-ui",
    "sql" + "ite",
    "Cloud" + "flare",
    "cloud" + "flare",
]
paths = [
    Path("reports/replay/2026-06-04_A股日报_完整版_replay.md"),
    Path("reports/replay/2026-06-05_A股日报_完整版_replay.md"),
    *Path("scripts/report").rglob("*.py"),
    *Path("scripts/selection").rglob("*.py"),
]
hits = []
for path in paths:
    if not path.exists() or not path.is_file():
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for term in terms:
        if term in text:
            hits.append(f"{path}: {term}")
if hits:
    print("\n".join(hits))
    raise SystemExit(1)
PY
```

预期：没有命中。若命中历史文档或颜色值误报，记录并确认不在日报输出和运行路径。

- [ ] **步骤 5：检查 0% 时没有新增参与路径**

运行：

```bash
rg -n "最终标的解题过程|明日执行对象|50%条件执行|100%核心进攻|0%不参与|无执行对象" reports/replay/2026-06-05_A股日报_完整版_replay.md
```

预期：若 2026-06-05 为 0%，不出现新增参与路径；只允许无执行对象、观察流水或旧仓处理。

---

### 任务 14：最终质量检查

**文件：**
- 全部改动文件

- [ ] **步骤 1：运行语法检查**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m py_compile \
  scripts/report/selection_workflow.py \
  scripts/report/runtime.py \
  scripts/report/two_layer_decision_payload.py \
  scripts/report/sniper_target_derivation.py \
  scripts/selection/candidate_trace_contracts.py \
  scripts/report/report_acceptance_audit.py
```

预期：无输出。

- [ ] **步骤 2：运行 diff 空白检查**

运行：

```bash
git diff --check
```

预期：无输出。

- [ ] **步骤 3：查看改动范围**

运行：

```bash
git status --short scripts/report/selection_workflow.py tests/test_selection_workflow.py tests/test_selection_workflow_flowchart.py scripts/report/runtime.py scripts/report/two_layer_decision_payload.py scripts/report/sniper_target_derivation.py scripts/selection/candidate_trace_contracts.py scripts/report/report_acceptance_audit.py tests/test_report_runtime.py tests/test_two_layer_decision_payload.py tests/test_candidate_trace_contracts.py tests/test_report_acceptance_audit.py
```

预期：只包含本计划相关文件。不要处理无关脏文件。

---

## 计划自检

- Spec 覆盖：N0-N9、候选生命周期、反推龙头、唯一最终对象、0/50/100 仓位、双层决策、候选追踪、流程图和 replay 验证均有任务覆盖。
- 占位扫描：计划没有未定义步骤；只有任务 11 的真实脚本路径需要先用 `rg` 定位，这是执行步骤的一部分，不是缺失实现。
- 类型一致性：核心结构统一为 `selection_workflow`、`nodes`、`candidate_pool`、`final`、`flowchart_payload`；最终对象统一使用 `final.execution_object`。
- 范围控制：不接入外部工作流平台，不改 HTML 样式，不恢复废弃路径，不新增仓位层级。
