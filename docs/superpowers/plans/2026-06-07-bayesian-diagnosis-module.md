# 贝叶斯诊断模块实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 按已批准 spec 实现 `bayesian_diagnosis.v1`，让日报用同一条市场路径诊断出唯一执行对象、诊断标签和 0%/50%/100% 仓位，并禁止概率区间式伪精确输出。

**实现思路：** 第一版不重写选股引擎，只新增一个纯函数诊断包，把市场、主线/板块、资金、候选、旧评分和反证收编成路径摘要。运行时生成并存储该包，再让 `final_target_resolution`、`sniper_target_derivation`、首页、附录和验收检查共同消费同一份结果。每一步先写聚焦测试，再做最小实现。

**技术栈：** Python 3.14、`unittest`、现有日报运行链路、PostgreSQL 事实库既有快照、Markdown 渲染与 `report_acceptance_audit`。

---

## 已确认范围

范围内：

- 新增 `scripts/report/bayesian_diagnosis.py`，输出 `bayesian_diagnosis.v1`。
- 新增 `tests/test_bayesian_diagnosis.py`。
- 修改 `scripts/report/runtime.py`，在运行时生成、存储并传递诊断包。
- 修改 `scripts/report/sniper_target_derivation.py`，让最终标的传导链读取诊断结论和路径摘要。
- 修改 `scripts/report/front_page_v2_renderer.py`，在首页展示简版诊断结论。
- 修改 `scripts/report/report_acceptance_audit.py` 和相关测试，检查概率区间、路径摘要、局部一致性、分段组合一致性。
- 修改最小必要的现有测试。

范围外：

- 不训练概率模型。
- 不输出概率区间或粗概率标签。
- 不新增 25%、30%、70% 仓位。
- 不删除仍有证据价值的旧评分代码。
- 不改动 PostgreSQL 数据模型。
- 不恢复 sqlite、Cloudflare、snap-ui 路径。

## 文件结构

- 新建：`scripts/report/bayesian_diagnosis.py`
  - 负责构建 `bayesian_diagnosis.v1` 纯函数包。
  - 负责诊断标签、路径摘要、候选池、旧评分冲突、行动落点。
  - 不渲染 Markdown。

- 新建：`tests/test_bayesian_diagnosis.py`
  - 覆盖市场冰点、板块强个股弱、个股强板块弱、三层共振、旧评分冲突、大市值资金阈值。

- 修改：`scripts/report/runtime.py`
  - 导入并调用 `build_bayesian_diagnosis_packet`。
  - 新增 `_store_runtime_bayesian_diagnosis`。
  - 把诊断包写入 `data`、`execution_stage_context`、`market_research_snapshot`。
  - 让 `final_target_resolution`、`sniper_target_derivation`、首页快照能消费它。

- 修改：`scripts/report/sniper_target_derivation.py`
  - `build_sniper_target_derivation_packet` 增加可选 `bayesian_diagnosis=None`。
  - `render_full_ascii` 或新增 section 在完整路径中展示诊断路径摘要。
  - 旧候选仍显示为过程证据，但最终原因优先来自诊断包。

- 修改：`scripts/report/front_page_v2_renderer.py`
  - 新增 `_bayesian_diagnosis(snapshot)` 和 `_bayesian_diagnosis_front_lines(snapshot)`。
  - 在最终标的传导链之前展示 `### 明日诊断结论`。
  - 首页禁止概率区间。

- 修改：`scripts/report/report_acceptance_audit.py`
  - 新增概率区间/粗概率标签检查。
  - 新增诊断路径摘要检查。
  - 新增局部一致性和分段组合一致性检查。

- 修改：`tests/test_front_page_v2_renderer.py`
  - 覆盖首页诊断结论展示和不展示概率区间。

- 修改：`tests/test_report_acceptance_audit.py`
  - 覆盖缺少诊断路径、概率区间、首页对象与诊断对象不一致、路径日期缺失。

- 修改：`tests/test_report_runtime.py`
  - 覆盖运行时存储 `bayesian_diagnosis` 并传给 `sniper_target_derivation`。

---

### 任务 1：新增贝叶斯诊断纯函数包

**文件：**
- 新建：`scripts/report/bayesian_diagnosis.py`
- 新建：`tests/test_bayesian_diagnosis.py`

- [ ] **步骤 1：写失败测试，覆盖三层共振输出 100%**

在 `tests/test_bayesian_diagnosis.py` 新增：

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.bayesian_diagnosis import build_bayesian_diagnosis_packet


class BayesianDiagnosisTest(unittest.TestCase):
    def test_three_layer_resonance_allows_high_confidence_100(self):
        packet = build_bayesian_diagnosis_packet(
            target_date="2026-06-04",
            market_research_snapshot={
                "target_date": "2026-06-04",
                "market_state_snapshot": {
                    "market_state": "修复",
                    "leading_line": "电力",
                    "up_count": 3600,
                    "down_count": 1200,
                    "limit_up_count": 78,
                    "limit_down_count": 3,
                },
                "mainline_turnover_summary": {
                    "current_mainline": "电力",
                    "primary_line": "电力",
                    "mainline_cycle_stage": "发酵",
                    "overtake_window_summary": {"window_state": "窗口打开", "summary": "电力比预期更强"},
                },
            },
            final_target_resolution={
                "display_target": {"code": "001896", "name": "豫能控股", "sector": "电力"},
                "new_entry_target": {"code": "001896", "name": "豫能控股", "sector": "电力"},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": "新开仓对象具备执行资格"},
            },
            position_decision={
                "target_position_pct": 100,
                "full_attack_ready": True,
                "full_attack_check": {"status": "ready", "missing": []},
                "support_price": 8.10,
            },
            execution_stage_context={
                "best_stock": {
                    "code": "001896",
                    "name": "豫能控股",
                    "sector": "电力",
                    "quality_role": "板块龙头",
                    "acceptance_ready": True,
                    "participation_window": "09:50-10:10",
                    "large_order_net_inflow": 128000000,
                    "float_market_cap": 18000000000,
                },
                "candidate_quality_samples": [],
            },
        )

        self.assertEqual(packet["schema_version"], "bayesian_diagnosis.v1")
        self.assertEqual(packet["conclusion"]["diagnosis_label"], "高可信")
        self.assertEqual(packet["conclusion"]["position_pct"], 100)
        self.assertEqual(packet["conclusion"]["execution_object"]["code"], "001896")
        self.assertEqual([step["layer"] for step in packet["path"]], ["market", "mainline", "capital", "stock", "counter_evidence"])
        self.assertTrue(all(step.get("source_date") == "2026-06-04" for step in packet["path"]))
        self.assertFalse(packet["score_conflicts"])
```

- [ ] **步骤 2：运行测试，确认模块不存在导致失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_bayesian_diagnosis.BayesianDiagnosisTest.test_three_layer_resonance_allows_high_confidence_100
```

预期：失败，错误包含：

```text
ModuleNotFoundError: No module named 'report.bayesian_diagnosis'
```

- [ ] **步骤 3：写最小实现文件和三层共振逻辑**

新建 `scripts/report/bayesian_diagnosis.py`：

```python
from __future__ import annotations

SCHEMA_VERSION = "bayesian_diagnosis.v1"
DIAGNOSIS_LABEL_LOW = "低可信"
DIAGNOSIS_LABEL_MID = "中高可信"
DIAGNOSIS_LABEL_HIGH = "高可信"


def _clean_text(value, default=""):
    text = " ".join(str(value or "").replace("|", "｜").split()).strip()
    return text if text else default


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace("%", "").strip()))
    except (TypeError, ValueError):
        return default


def _stock_payload(value):
    if not isinstance(value, dict):
        return {}
    code = _clean_text(value.get("code") or value.get("stock_code") or value.get("代码") or value.get("symbol"))
    if "." in code:
        code = code.split(".", 1)[0]
    digits = "".join(ch for ch in code if ch.isdigit())
    code = digits[-6:] if len(digits) >= 6 else code
    name = _clean_text(value.get("name") or value.get("stock_name") or value.get("名称"))
    if not (code or name):
        return {}
    payload = {"code": code, "name": name}
    sector = _clean_text(value.get("sector") or value.get("sector_name") or value.get("industry") or value.get("板块"))
    if sector:
        payload["sector"] = sector
    return payload


def _stock_key(value):
    payload = _stock_payload(value)
    return payload.get("code") or payload.get("name") or ""


def _first_stock(*values):
    for value in values:
        payload = _stock_payload(value)
        if payload:
            return payload
    return {}


def _target_from_resolution(final_target_resolution):
    resolution = final_target_resolution if isinstance(final_target_resolution, dict) else {}
    return _first_stock(
        resolution.get("display_target"),
        resolution.get("new_entry_target"),
        resolution.get("watch_target"),
        resolution.get("process_target"),
    )


def _market_snapshot(market_research_snapshot):
    snapshot = market_research_snapshot if isinstance(market_research_snapshot, dict) else {}
    state = snapshot.get("market_state_snapshot") if isinstance(snapshot.get("market_state_snapshot"), dict) else {}
    if not state and isinstance(snapshot.get("state_machine"), dict):
        state = snapshot.get("state_machine")
    return snapshot, state


def _mainline_summary(snapshot):
    summary = snapshot.get("mainline_turnover_summary") if isinstance(snapshot.get("mainline_turnover_summary"), dict) else {}
    if not summary and isinstance(snapshot.get("mainline_capacity_regime_summary"), dict):
        summary = snapshot.get("mainline_capacity_regime_summary")
    return summary


def _market_is_ice(state):
    text = " ".join(_clean_text(state.get(key)) for key in ("market_state", "state_code", "execution_bias", "summary"))
    if "冰点" in text or "退潮" in text:
        return True
    down = _safe_int(state.get("down_count"))
    up = _safe_int(state.get("up_count"))
    limit_down = _safe_int(state.get("limit_down_count") or state.get("dt_count"))
    return bool((down >= 4000 and up <= 1000) or limit_down >= 30)


def _mainline_is_supportive(summary, target):
    target_sector = _clean_text(target.get("sector"))
    line = _clean_text(
        summary.get("current_mainline")
        or summary.get("primary_line")
        or summary.get("primary_mainline")
        or summary.get("cycle_mainline")
    )
    stage = _clean_text(summary.get("mainline_cycle_stage") or summary.get("cycle_stage") or summary.get("主线阶段"))
    if "冰点" in stage or "退潮" in stage:
        return False, line, stage
    if target_sector and line and (target_sector in line or line in target_sector):
        return True, line, stage
    window = summary.get("overtake_window_summary") if isinstance(summary.get("overtake_window_summary"), dict) else {}
    window_text = _clean_text(window.get("summary") or window.get("window_state"))
    if target_sector and target_sector in window_text and "强" in window_text:
        return True, line or target_sector, stage
    return False, line, stage


def _candidate_for_target(execution_stage_context, target):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    target_key = _stock_key(target)
    for key in ("best_stock", "watch_anchor", "selected_position_candidate", "current_core_candidate"):
        candidate = context.get(key)
        if _stock_key(candidate) and _stock_key(candidate) == target_key:
            return candidate
    for key in ("candidate_quality_samples", "scored_executable_stocks", "scored_waiting_stocks", "waiting_stocks"):
        rows = context.get(key)
        if isinstance(rows, list):
            for row in rows:
                if _stock_key(row) and _stock_key(row) == target_key:
                    return row
    return {}


def _candidate_is_leader(candidate):
    text = " ".join(
        _clean_text(candidate.get(key))
        for key in ("quality_role", "role", "identity", "reason", "watch_anchor_note", "conviction_reason")
    )
    return any(marker in text for marker in ("龙头", "核心", "板块锚", "情绪锚", "容量核心"))


def _candidate_has_acceptance(candidate):
    if any(candidate.get(key) for key in ("acceptance_ready", "acceptance_act_right", "stock_acceptance")):
        return True
    text = " ".join(_clean_text(candidate.get(key)) for key in ("acceptance_state", "abnormal_summary", "reason", "watch_anchor_note"))
    return any(marker in text for marker in ("承接", "跌不下去", "回封", "VWAP", "0轴", "MA5"))


def _candidate_has_window(candidate):
    text = " ".join(
        _clean_text(candidate.get(key))
        for key in ("participation_window", "entry_window", "execution_window", "auction_script", "first_minutes_script")
    )
    return any(window in text for window in ("09:30-09:35", "09:50-10:10", "14:30-14:55"))


def _candidate_has_invalidation(candidate, position_decision):
    if isinstance(position_decision, dict) and position_decision.get("support_price") not in (None, ""):
        return True
    stop_plan = candidate.get("stop_plan") if isinstance(candidate.get("stop_plan"), dict) else {}
    for key in ("failure_line", "stop_price", "stop_loss_price", "invalidation_price", "support_price"):
        if candidate.get(key) not in (None, "") or stop_plan.get(key) not in (None, ""):
            return True
    return False


def _capital_threshold(candidate):
    market_cap = _safe_int(candidate.get("float_market_cap") or candidate.get("market_cap"))
    turnover = _safe_int(candidate.get("turnover_amount") or candidate.get("amount"))
    large_order = _safe_int(candidate.get("large_order_net_inflow") or candidate.get("main_net_inflow"))
    if market_cap >= 50_000_000_000 or turnover >= 5_000_000_000:
        return 100_000_000, large_order, "大市值或高成交核心"
    return 30_000_000, large_order, "小中盘活跃股"


def _path_step(*, layer, target_date, input_summary, judgement, passes_forward, cannot_conclude, conflicts=None):
    return {
        "layer": layer,
        "source_date": target_date,
        "input_summary": [text for text in input_summary if text],
        "judgement": judgement,
        "passes_forward": passes_forward,
        "cannot_conclude": [text for text in cannot_conclude if text],
        "conflicts": list(conflicts or []),
    }


def _score_conflicts(execution_stage_context, target):
    context = execution_stage_context if isinstance(execution_stage_context, dict) else {}
    target_key = _stock_key(target)
    conflicts = []
    for key in ("best_stock", "watch_anchor"):
        candidate = context.get(key)
        if _stock_key(candidate) and target_key and _stock_key(candidate) != target_key:
            conflicts.append(
                {
                    "source": key,
                    "old_signal": _stock_label(candidate),
                    "diagnosis_resolution": "只作为过程候选证据，不决定最终仓位",
                }
            )
    return conflicts


def _stock_label(value):
    payload = _stock_payload(value)
    name = payload.get("name", "")
    code = payload.get("code", "")
    if name and code:
        return f"{name}({code})"
    return name or code or "暂无"


def _candidate_pool_rows(execution_stage_context, target, score_conflicts):
    rows = []
    if target:
        rows.append(
            {
                "candidate": dict(target),
                "role": "条件执行对象",
                "kept_or_rejected": "保留",
                "reason": "路径诊断保留为明日唯一对象",
                "counter_evidence": [],
            }
        )
    for conflict in score_conflicts:
        rows.append(
            {
                "candidate": {"name": conflict.get("old_signal", "")},
                "role": "过程候选",
                "kept_or_rejected": "被淘汰",
                "reason": conflict.get("diagnosis_resolution", "只作为过程证据"),
                "counter_evidence": ["未通过同一诊断路径"],
            }
        )
    return rows


def build_bayesian_diagnosis_packet(
    *,
    target_date="",
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    position_decision=None,
):
    target_date = _clean_text(target_date or (data or {}).get("target_date") or (market_research_snapshot or {}).get("target_date"))
    snapshot, market_state = _market_snapshot(market_research_snapshot)
    summary = _mainline_summary(snapshot)
    target = _target_from_resolution(final_target_resolution)
    candidate = _candidate_for_target(execution_stage_context, target)
    if not candidate and target:
        candidate = dict(target)

    market_ice = _market_is_ice(market_state)
    mainline_ok, mainline, mainline_stage = _mainline_is_supportive(summary, target)
    leader = _candidate_is_leader(candidate)
    acceptance = _candidate_has_acceptance(candidate)
    window = _candidate_has_window(candidate)
    invalidation = _candidate_has_invalidation(candidate, position_decision if isinstance(position_decision, dict) else {})
    threshold, large_order, capital_tier = _capital_threshold(candidate)
    capital_ok = large_order >= threshold if large_order else False
    position_pct = _safe_int((position_decision or {}).get("target_position_pct")) if isinstance(position_decision, dict) else 0
    full_ready = bool(isinstance(position_decision, dict) and position_decision.get("full_attack_ready"))

    counter_evidence = []
    if market_ice:
        counter_evidence.append("市场或赚钱效应处于冰点")
    if not mainline_ok:
        counter_evidence.append("主线/板块路径未确认")
    if not leader:
        counter_evidence.append("未证明是真龙头")
    if not acceptance:
        counter_evidence.append("承接证据不足")
    if not window:
        counter_evidence.append("缺少固定交易窗口条件")
    if large_order and not capital_ok:
        counter_evidence.append(f"资金确认不足，{capital_tier}需要更高确认")
    if position_pct >= 100 and not invalidation:
        counter_evidence.append("缺少失效价")

    if not target or market_ice or counter_evidence:
        diagnosis_label = DIAGNOSIS_LABEL_LOW if not target or market_ice or not mainline_ok else DIAGNOSIS_LABEL_MID
        if position_pct >= 100 and counter_evidence:
            position_pct = 50 if not market_ice and mainline_ok and target else 0
    elif position_pct >= 100 and full_ready and mainline_ok and leader and acceptance and window and invalidation:
        diagnosis_label = DIAGNOSIS_LABEL_HIGH
        position_pct = 100
    else:
        diagnosis_label = DIAGNOSIS_LABEL_MID
        position_pct = 50 if target else 0

    if diagnosis_label == DIAGNOSIS_LABEL_LOW:
        action_text = "0%不参与"
        position_pct = 0
    elif diagnosis_label == DIAGNOSIS_LABEL_HIGH:
        action_text = "三层共振才100%准备"
    else:
        action_text = "条件满足才50%，失败回到0%"
        position_pct = 50 if target else 0

    path = [
        _path_step(
            layer="market",
            target_date=target_date,
            input_summary=[
                f"市场状态：{_clean_text(market_state.get('market_state') or market_state.get('state_code'), '未知')}",
                f"涨跌家数：{market_state.get('up_count', '-')}/{market_state.get('down_count', '-')}",
            ],
            judgement="市场冰点，停止进攻诊断" if market_ice else "市场未否定继续诊断",
            passes_forward="不参与" if market_ice else "允许继续诊断",
            cannot_conclude=["不能直接选出个股"],
        ),
        _path_step(
            layer="mainline",
            target_date=target_date,
            input_summary=[f"主线：{mainline or '未知'}", f"主线阶段：{mainline_stage or '未知'}"],
            judgement="主线/板块支持目标方向" if mainline_ok else "主线/板块未支持目标方向",
            passes_forward="目标方向可进入候选池" if mainline_ok else "只能保留过程候选",
            cannot_conclude=["不能直接指定任意涨停股"],
        ),
        _path_step(
            layer="capital",
            target_date=target_date,
            input_summary=[f"资金体量：{capital_tier}", f"大单净流入：{large_order or '缺失'}"],
            judgement="资金确认满足体量要求" if capital_ok else "资金确认不足或缺失",
            passes_forward="资金支持个股诊断" if capital_ok else "主动进攻路径不能成立",
            cannot_conclude=["资金不能单独选最终对象"],
        ),
        _path_step(
            layer="stock",
            target_date=target_date,
            input_summary=[f"候选：{_stock_label(target)}", f"龙头证据：{'有' if leader else '不足'}", f"承接：{'有' if acceptance else '不足'}"],
            judgement="个股具备执行资格" if leader and acceptance and window else "个股执行资格不足",
            passes_forward="进入反证复核" if leader and acceptance and window else "不能升为明日执行对象",
            cannot_conclude=["涨停本身不是龙头资格"],
        ),
        _path_step(
            layer="counter_evidence",
            target_date=target_date,
            input_summary=counter_evidence or ["未发现压倒性反证"],
            judgement="反证压低行动档位" if counter_evidence else "反证未推翻路径",
            passes_forward=action_text,
            cannot_conclude=["不能用弱支持证据覆盖关键反证"],
        ),
    ]
    conflicts = _score_conflicts(execution_stage_context, target)
    if conflicts:
        path[-1]["conflicts"] = [item["diagnosis_resolution"] for item in conflicts]

    return {
        "schema_version": SCHEMA_VERSION,
        "target_date": target_date,
        "conclusion": {
            "execution_object": dict(target),
            "execution_identity": "明日执行对象" if target and position_pct > 0 else "无明日执行对象",
            "diagnosis_label": diagnosis_label,
            "position_pct": position_pct,
            "action_text": action_text,
            "fail_action": "不参与",
        },
        "path": path,
        "candidate_pool": _candidate_pool_rows(execution_stage_context, target, conflicts),
        "score_conflicts": conflicts,
        "counter_evidence": counter_evidence,
    }
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_bayesian_diagnosis.BayesianDiagnosisTest.test_three_layer_resonance_allows_high_confidence_100
```

预期：PASS。

- [ ] **步骤 5：追加失败测试，覆盖市场冰点压到 0%**

在 `BayesianDiagnosisTest` 中追加：

```python
    def test_market_ice_point_forces_zero_even_with_candidate(self):
        packet = build_bayesian_diagnosis_packet(
            target_date="2026-06-05",
            market_research_snapshot={
                "target_date": "2026-06-05",
                "market_state_snapshot": {
                    "market_state": "冰点",
                    "up_count": 500,
                    "down_count": 4600,
                    "limit_down_count": 45,
                },
                "mainline_turnover_summary": {"current_mainline": "电力", "mainline_cycle_stage": "冰点"},
            },
            final_target_resolution={"display_target": {"code": "600000", "name": "样本股", "sector": "电力"}},
            position_decision={"target_position_pct": 50},
            execution_stage_context={"best_stock": {"code": "600000", "name": "样本股", "sector": "电力", "quality_role": "龙头"}},
        )

        self.assertEqual(packet["conclusion"]["diagnosis_label"], "低可信")
        self.assertEqual(packet["conclusion"]["position_pct"], 0)
        self.assertIn("市场或赚钱效应处于冰点", packet["counter_evidence"])
        self.assertEqual(packet["path"][0]["passes_forward"], "不参与")
```

- [ ] **步骤 6：运行新增测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_bayesian_diagnosis
```

预期：PASS。

- [ ] **步骤 7：提交任务 1**

```bash
git add scripts/report/bayesian_diagnosis.py tests/test_bayesian_diagnosis.py
git commit -m "feat(report): add bayesian diagnosis packet"
```

---

### 任务 2：运行时生成并存储诊断包

**文件：**
- 修改：`scripts/report/runtime.py:59-63`
- 修改：`scripts/report/runtime.py:2307-2344`
- 修改：`scripts/report/runtime.py:6546-6593`
- 修改：`scripts/report/runtime.py:6819-6877`
- 测试：`tests/test_report_runtime.py`

- [ ] **步骤 1：写失败测试，确认运行时 helper 存储诊断包**

在 `tests/test_report_runtime.py` 中追加或放到现有 runtime helper 测试类：

```python
    def test_store_runtime_bayesian_diagnosis_writes_all_contexts(self):
        from report.runtime import _store_runtime_bayesian_diagnosis

        data = {}
        execution_stage_context = {}
        market_research_snapshot = {}
        packet = {"schema_version": "bayesian_diagnosis.v1", "target_date": "2026-06-04"}

        stored = _store_runtime_bayesian_diagnosis(
            packet,
            data=data,
            execution_stage_context=execution_stage_context,
            market_research_snapshot=market_research_snapshot,
        )

        self.assertEqual(stored, packet)
        self.assertEqual(data["bayesian_diagnosis"], packet)
        self.assertEqual(execution_stage_context["bayesian_diagnosis"], packet)
        self.assertEqual(market_research_snapshot["bayesian_diagnosis"], packet)
        self.assertIs(data["market_research_snapshot"], market_research_snapshot)
        self.assertIs(data["execution_stage_context"], execution_stage_context)
```

- [ ] **步骤 2：运行测试，确认 helper 不存在导致失败**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_store_runtime_bayesian_diagnosis_writes_all_contexts
```

如果类名不是 `ReportRuntimeTest`，用 `rg -n "class .*Runtime" tests/test_report_runtime.py` 找到实际类名后替换命令。

预期：FAIL，错误包含：

```text
ImportError: cannot import name '_store_runtime_bayesian_diagnosis'
```

- [ ] **步骤 3：在 runtime 导入诊断构建器**

在 `scripts/report/runtime.py` 顶部已有 `report.sniper_target_derivation` 导入附近添加：

```python
from report.bayesian_diagnosis import build_bayesian_diagnosis_packet
```

- [ ] **步骤 4：新增构建和存储 helper**

在 `_store_runtime_sniper_target_derivation` 前后添加：

```python
def _build_bayesian_diagnosis_packet(
    *,
    data=None,
    execution_stage_context=None,
    market_research_snapshot=None,
    final_target_resolution=None,
    position_decision=None,
    target_date="",
):
    return build_bayesian_diagnosis_packet(
        target_date=target_date or ((data or {}).get("target_date") if isinstance(data, dict) else ""),
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
    )


def _store_runtime_bayesian_diagnosis(packet, data=None, execution_stage_context=None, market_research_snapshot=None):
    if not isinstance(packet, dict) or not packet:
        return {}
    stored = dict(packet)
    for target in (data, execution_stage_context, market_research_snapshot):
        if isinstance(target, dict):
            target["bayesian_diagnosis"] = stored
    if isinstance(data, dict) and isinstance(market_research_snapshot, dict):
        data["market_research_snapshot"] = market_research_snapshot
    if isinstance(data, dict) and isinstance(execution_stage_context, dict):
        data["execution_stage_context"] = execution_stage_context
    if isinstance(execution_stage_context, dict) and isinstance(market_research_snapshot, dict):
        execution_stage_context["market_research_snapshot"] = market_research_snapshot
    return stored
```

- [ ] **步骤 5：运行 helper 测试，确认通过**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime.ReportRuntimeTest.test_store_runtime_bayesian_diagnosis_writes_all_contexts
```

预期：PASS。

- [ ] **步骤 6：在两处运行时链路生成诊断包**

在两段已有代码中，均放在 `_store_runtime_final_target_resolution(...)` 之后、`build_two_layer_decision_payload(...)` 之前：

```python
    bayesian_diagnosis = _build_bayesian_diagnosis_packet(
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
        final_target_resolution=final_target_resolution,
        position_decision=position_decision,
        target_date=target_date,
    )
    _store_runtime_bayesian_diagnosis(
        bayesian_diagnosis,
        data=data,
        execution_stage_context=execution_stage_context,
        market_research_snapshot=market_research_snapshot,
    )
```

同时在 `front_page_market_research_snapshot = { ... }` 中加入：

```python
        "bayesian_diagnosis": bayesian_diagnosis,
```

- [ ] **步骤 7：运行相关 runtime 和诊断测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_bayesian_diagnosis tests.test_report_runtime
```

预期：PASS。

- [ ] **步骤 8：提交任务 2**

```bash
git add scripts/report/runtime.py tests/test_report_runtime.py
git commit -m "feat(report): store bayesian diagnosis in runtime"
```

---

### 任务 3：让最终标的传导链接入诊断路径

**文件：**
- 修改：`scripts/report/sniper_target_derivation.py:412-504`
- 修改：`scripts/report/sniper_target_derivation.py:532-606`
- 修改：`scripts/report/runtime.py:2307-2328`
- 测试：`tests/test_sniper_target_derivation.py` 或新建该文件

- [ ] **步骤 1：写失败测试，诊断路径出现在完整路径图**

如果没有 `tests/test_sniper_target_derivation.py`，新建：

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.sniper_target_derivation import build_sniper_target_derivation_packet, full_section


class SniperTargetDerivationBayesianDiagnosisTest(unittest.TestCase):
    def test_full_section_includes_bayesian_diagnosis_path(self):
        diagnosis = {
            "schema_version": "bayesian_diagnosis.v1",
            "target_date": "2026-06-04",
            "conclusion": {
                "execution_object": {"code": "001896", "name": "豫能控股"},
                "diagnosis_label": "中高可信",
                "position_pct": 50,
                "action_text": "条件满足才50%，失败回到0%",
            },
            "path": [
                {
                    "layer": "market",
                    "source_date": "2026-06-04",
                    "input_summary": ["市场未否定继续诊断"],
                    "judgement": "市场未否定继续诊断",
                    "passes_forward": "允许继续诊断",
                    "cannot_conclude": ["不能直接选出个股"],
                    "conflicts": [],
                },
                {
                    "layer": "stock",
                    "source_date": "2026-06-04",
                    "input_summary": ["候选：豫能控股(001896)"],
                    "judgement": "个股具备执行资格",
                    "passes_forward": "进入反证复核",
                    "cannot_conclude": ["涨停本身不是龙头资格"],
                    "conflicts": [],
                },
            ],
        }
        packet = build_sniper_target_derivation_packet(
            final_target_resolution={
                "display_target": {"code": "001896", "name": "豫能控股"},
                "capital_priority_decision": {"capital_priority": "new_entry", "reason": "诊断路径保留"},
            },
            position_decision={"target_position_pct": 50},
            bayesian_diagnosis=diagnosis,
            target_date="2026-06-04",
        )

        rendered = "\n".join(full_section(packet))

        self.assertIn("贝叶斯诊断路径", rendered)
        self.assertIn("诊断标签=中高可信", rendered)
        self.assertIn("market", rendered)
        self.assertIn("不能直接选出个股", rendered)
```

- [ ] **步骤 2：运行测试，确认参数不支持或内容缺失导致失败**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_sniper_target_derivation.SniperTargetDerivationBayesianDiagnosisTest.test_full_section_includes_bayesian_diagnosis_path
```

预期：FAIL，可能是：

```text
TypeError: build_sniper_target_derivation_packet() got an unexpected keyword argument 'bayesian_diagnosis'
```

- [ ] **步骤 3：修改 `build_sniper_target_derivation_packet` 签名和 packet**

在函数参数中增加：

```python
    bayesian_diagnosis=None,
```

在 `packet = { ... }` 中增加：

```python
        "bayesian_diagnosis": dict(bayesian_diagnosis or {}) if isinstance(bayesian_diagnosis, dict) else {},
```

- [ ] **步骤 4：新增诊断路径渲染 helper**

在 `render_full_ascii` 前添加：

```python
def _render_bayesian_diagnosis_lines(packet):
    diagnosis = packet.get("bayesian_diagnosis") if isinstance(packet, dict) else {}
    if not isinstance(diagnosis, dict) or diagnosis.get("schema_version") != "bayesian_diagnosis.v1":
        return []
    conclusion = diagnosis.get("conclusion") if isinstance(diagnosis.get("conclusion"), dict) else {}
    lines = [
        "贝叶斯诊断路径",
        "|-- 诊断标签={label} 仓位={position_pct}% 动作={action}".format(
            label=clean_text(conclusion.get("diagnosis_label"), "-"),
            position_pct=conclusion.get("position_pct", 0),
            action=clean_text(conclusion.get("action_text"), "-"),
        ),
    ]
    for step in diagnosis.get("path") or []:
        if not isinstance(step, dict):
            continue
        lines.append(
            "|-- 层级={layer} 日期={source_date} 判断={judgement} 传递={passes_forward}".format(
                layer=clean_text(step.get("layer"), "-"),
                source_date=clean_text(step.get("source_date"), "-"),
                judgement=clean_text(step.get("judgement"), "-"),
                passes_forward=clean_text(step.get("passes_forward"), "-"),
            )
        )
        cannot = "；".join(clean_text(item) for item in (step.get("cannot_conclude") or []) if clean_text(item))
        if cannot:
            lines.append(f"|   不能推出={cannot}")
    return lines
```

- [ ] **步骤 5：在完整路径图中插入诊断路径**

在 `render_full_ascii(packet)` 中 `lines = []` 后添加：

```python
    diagnosis_lines = _render_bayesian_diagnosis_lines(packet)
    if diagnosis_lines:
        lines.extend(diagnosis_lines)
        lines.append("|")
```

- [ ] **步骤 6：runtime wrapper 传入诊断包**

修改 `_build_sniper_target_derivation_packet(...)` wrapper，增加参数：

```python
    bayesian_diagnosis=None,
```

调用 `build_sniper_target_derivation_packet(...)` 时传入：

```python
        bayesian_diagnosis=bayesian_diagnosis,
```

两处调用 `_build_sniper_target_derivation_packet(...)` 时加入：

```python
        bayesian_diagnosis=bayesian_diagnosis,
```

- [ ] **步骤 7：运行测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_sniper_target_derivation tests.test_bayesian_diagnosis tests.test_report_runtime
```

预期：PASS。

- [ ] **步骤 8：提交任务 3**

```bash
git add scripts/report/sniper_target_derivation.py scripts/report/runtime.py tests/test_sniper_target_derivation.py
git commit -m "feat(report): include bayesian diagnosis in target derivation"
```

---

### 任务 4：首页渲染诊断结论

**文件：**
- 修改：`scripts/report/front_page_v2_renderer.py:1493-1500`
- 修改：`scripts/report/front_page_v2_renderer.py:2767-2810`
- 测试：`tests/test_front_page_v2_renderer.py`

- [ ] **步骤 1：写失败测试，首页展示诊断结论且不展示概率区间**

在 `tests/test_front_page_v2_renderer.py` 中追加：

```python
    def test_front_page_renders_bayesian_diagnosis_summary_without_probability_band(self):
        lines = render_front_page_v2(
            [],
            target_date="2026-06-04",
            market_research_snapshot={
                "bayesian_diagnosis": {
                    "schema_version": "bayesian_diagnosis.v1",
                    "conclusion": {
                        "execution_object": {"code": "001896", "name": "豫能控股"},
                        "execution_identity": "明日执行对象",
                        "diagnosis_label": "中高可信",
                        "position_pct": 50,
                        "action_text": "条件满足才50%，失败回到0%",
                        "fail_action": "不参与",
                    },
                    "path": [
                        {"layer": "market", "judgement": "市场未否定继续诊断"},
                        {"layer": "mainline", "judgement": "主线/板块支持目标方向"},
                        {"layer": "stock", "judgement": "个股具备执行资格"},
                    ],
                    "counter_evidence": ["资金确认仍需次日验证"],
                },
                "sniper_target_derivation": {
                    "schema_version": "sniper_target_derivation.v1",
                    "canonical_target": {"code": "001896", "name": "豫能控股"},
                    "canonical_role": "执行对象",
                    "final_action": {"position_pct": 50, "action": "条件满足才参与"},
                    "steps": [],
                },
            },
            final_gate={},
        )
        markdown = "\n".join(lines)

        self.assertIn("### 明日诊断结论", markdown)
        self.assertIn("| 明日执行对象 | 豫能控股(001896) |", markdown)
        self.assertIn("| 诊断标签 | 中高可信 |", markdown)
        self.assertIn("| 仓位 | 条件满足才50%，失败回到0% |", markdown)
        self.assertIn("资金确认仍需次日验证", markdown)
        self.assertNotRegex(markdown, r"\d+%\s*-\s*\d+%")
```

- [ ] **步骤 2：运行测试，确认诊断区块缺失导致失败**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_front_page_renders_bayesian_diagnosis_summary_without_probability_band
```

如果类名不是 `FrontPageV2RendererTest`，用 `rg -n "class .*Front" tests/test_front_page_v2_renderer.py` 找实际类名后替换。

预期：FAIL，缺少 `### 明日诊断结论`。

- [ ] **步骤 3：新增首页诊断 helper**

在 `scripts/report/front_page_v2_renderer.py` 中 `_sniper_target_derivation(snapshot)` 附近添加：

```python
def _bayesian_diagnosis(snapshot):
    packet = (snapshot or {}).get("bayesian_diagnosis") or {}
    return packet if isinstance(packet, dict) and packet.get("schema_version") == "bayesian_diagnosis.v1" else {}


def _front_stock_label(stock):
    stock = stock if isinstance(stock, dict) else {}
    name = str(stock.get("name") or stock.get("stock_name") or stock.get("名称") or "").strip()
    code = str(stock.get("code") or stock.get("stock_code") or stock.get("代码") or "").strip()
    if "." in code:
        code = code.split(".", 1)[0]
    digits = "".join(ch for ch in code if ch.isdigit())
    code = digits[-6:] if len(digits) >= 6 else code
    if name and code:
        return f"{name}({code})"
    return name or code or "无"


def _bayesian_diagnosis_front_lines(snapshot):
    packet = _bayesian_diagnosis(snapshot)
    if not packet:
        return []
    conclusion = packet.get("conclusion") if isinstance(packet.get("conclusion"), dict) else {}
    target = conclusion.get("execution_object") if isinstance(conclusion.get("execution_object"), dict) else {}
    action_text = str(conclusion.get("action_text") or "不参与").strip()
    lines = [
        "### 明日诊断结论",
        "",
        "| 项目 | 结论 |",
        "|------|------|",
        f"| 明日是否参与 | {action_text} |",
        f"| 明日执行对象 | {_front_stock_label(target)} |",
        f"| 诊断标签 | {str(conclusion.get('diagnosis_label') or '低可信').strip()} |",
        f"| 仓位 | {action_text} |",
        f"| 失败处理 | {str(conclusion.get('fail_action') or '不参与').strip()} |",
    ]
    key_steps = []
    for step in packet.get("path") or []:
        if not isinstance(step, dict):
            continue
        judgement = str(step.get("judgement") or "").strip()
        layer = str(step.get("layer") or "").strip()
        if judgement:
            key_steps.append(f"{layer}：{judgement}")
    if key_steps:
        lines.extend(["", "#### 关键路径"])
        lines.extend(f"- {item}" for item in key_steps[:3])
    counter_evidence = [str(item).strip() for item in packet.get("counter_evidence") or [] if str(item).strip()]
    if counter_evidence:
        lines.extend(["", "#### 关键反证"])
        lines.extend(f"- {item}" for item in counter_evidence[:2])
    lines.append("")
    return lines
```

- [ ] **步骤 4：把诊断结论插入首页**

在 `render_front_page_v2(...)` 中，`compact_chain = _sniper_target_derivation_compact_section(...)` 前添加：

```python
    diagnosis_lines = _bayesian_diagnosis_front_lines(snapshot)
    if diagnosis_lines:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(diagnosis_lines)
```

- [ ] **步骤 5：运行首页测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_front_page_v2_renderer
```

预期：PASS。

- [ ] **步骤 6：提交任务 4**

```bash
git add scripts/report/front_page_v2_renderer.py tests/test_front_page_v2_renderer.py
git commit -m "feat(report): render bayesian diagnosis on front page"
```

---

### 任务 5：验收检查和 replay 验证

**文件：**
- 修改：`scripts/report/report_acceptance_audit.py`
- 修改：`tests/test_report_acceptance_audit.py`

- [ ] **步骤 1：写失败测试，概率区间判无效**

在 `ReportAcceptanceAuditTest` 中追加：

```python
    def test_audit_rejects_probability_band_in_bayesian_diagnosis(self):
        markdown = GOOD_MARKDOWN.replace(
            "## 明日账户建议\n",
            "### 明日诊断结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 诊断标签 | 40%-70%，中高可信 |\n\n"
            "## 明日账户建议\n",
            1,
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("bayesian_probability_band_forbidden", codes)
        self.assertFalse(result["passed"])
```

- [ ] **步骤 2：写失败测试，缺少路径摘要判无效**

追加：

```python
    def test_audit_rejects_bayesian_diagnosis_without_path_summary(self):
        markdown = GOOD_MARKDOWN.replace(
            "## 明日账户建议\n",
            "### 明日诊断结论\n"
            "| 项目 | 结论 |\n"
            "|------|------|\n"
            "| 明日执行对象 | 豫能控股(001896) |\n"
            "| 诊断标签 | 中高可信 |\n"
            "| 仓位 | 条件满足才50%，失败0% |\n\n"
            "## 明日账户建议\n",
            1,
        )

        result = audit_report_markdown(markdown)
        codes = {finding["code"] for finding in result["findings"]}

        self.assertIn("bayesian_path_summary_missing", codes)
        self.assertFalse(result["passed"])
```

- [ ] **步骤 3：运行测试，确认检查缺失导致失败**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_rejects_probability_band_in_bayesian_diagnosis tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_rejects_bayesian_diagnosis_without_path_summary
```

预期：FAIL，缺少对应 finding code。

- [ ] **步骤 4：实现验收检查**

在 `scripts/report/report_acceptance_audit.py` 中添加 helper：

```python
PROBABILITY_BAND_RE = re.compile(r"\b\d{1,3}%\s*[-~－—]\s*\d{1,3}%")
BAYESIAN_DIAGNOSIS_HEADING = "### 明日诊断结论"
BAYESIAN_PATH_REQUIRED_MARKERS = ("#### 关键路径", "贝叶斯诊断路径")


def _audit_bayesian_diagnosis_contract(lines):
    findings = []
    joined = "\n".join(str(line) for line in lines or [])
    for index, line in enumerate(lines or [], start=1):
        text = str(line)
        if PROBABILITY_BAND_RE.search(text):
            findings.append(
                _finding(
                    "bayesian_probability_band_forbidden",
                    "贝叶斯诊断模块不能展示概率区间或粗概率标签",
                    line=index,
                )
            )
    if BAYESIAN_DIAGNOSIS_HEADING in joined and not any(marker in joined for marker in BAYESIAN_PATH_REQUIRED_MARKERS):
        findings.append(
            _finding(
                "bayesian_path_summary_missing",
                "贝叶斯诊断结论缺少可复盘路径摘要",
            )
        )
    if "贝叶斯诊断路径" in joined:
        for marker in ("层级=market", "层级=mainline", "层级=stock"):
            if marker not in joined:
                findings.append(
                    _finding(
                        "bayesian_path_layer_missing",
                        f"贝叶斯诊断路径缺少{marker}",
                    )
                )
        if "日期=-" in joined:
            findings.append(
                _finding(
                    "bayesian_path_source_date_missing",
                    "贝叶斯诊断路径缺少事实来源日期",
                )
            )
    return findings
```

在 `audit_report_markdown(markdown, companion_html=None)` 中加入：

```python
    findings.extend(_audit_bayesian_diagnosis_contract(lines))
```

放在已有基础结构检查之后、返回结果之前。

- [ ] **步骤 5：运行验收测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit
```

预期：PASS。

- [ ] **步骤 6：运行本功能相关全部窄测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_bayesian_diagnosis \
  tests.test_sniper_target_derivation \
  tests.test_front_page_v2_renderer \
  tests.test_report_acceptance_audit \
  tests.test_report_runtime
```

预期：PASS。

- [ ] **步骤 7：运行 replay 生成检查 2026-06-04**

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
```

预期：命令成功，生成 `reports/replay/2026-06-04_A股日报_完整版_replay.md`。

- [ ] **步骤 8：运行 replay 生成检查 2026-06-05**

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

预期：命令成功，生成 `reports/replay/2026-06-05_A股日报_完整版_replay.md`。

- [ ] **步骤 9：对 replay 日报运行验收检查**

如果 `report_acceptance_audit.py` 支持 CLI，运行现有 CLI；如果不支持，用 Python 片段：

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
from report.report_acceptance_audit import audit_report_markdown
for path in [
    Path("reports/replay/2026-06-04_A股日报_完整版_replay.md"),
    Path("reports/replay/2026-06-05_A股日报_完整版_replay.md"),
]:
    result = audit_report_markdown(path.read_text(encoding="utf-8"))
    print(path, result["passed"])
    for finding in result["findings"]:
        print(finding)
    if not result["passed"]:
        raise SystemExit(1)
PY
```

预期：两份 replay 都输出 `True`。

- [ ] **步骤 10：运行空白和语义禁用词检查**

```bash
git diff --check
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path

patterns = [
    "20%-40%",
    "40%-70%",
    "70%+",
    "硬" + "门" + "禁",
    "门" + "禁",
    "hard " + "gate",
    "状态" + "机",
    "状态" + "机词汇",
]
targets = [
    Path("scripts/report"),
    Path("tests"),
    Path("docs/superpowers/specs/2026-06-07-bayesian-diagnosis-module-design.md"),
]
hits = []
for target in targets:
    files = [target] if target.is_file() else list(target.rglob("*"))
    for path in files:
        if path.is_dir() or path.suffix not in {".py", ".md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern in line for pattern in patterns):
                hits.append(f"{path}:{lineno}:{line}")
if hits:
    print("\n".join(hits))
    raise SystemExit(1)
PY
```

预期：`git diff --check` 无输出；`rg` 不应命中新改用户可见文字。若命中代码字段名，确认不是用户可见文案。

- [ ] **步骤 11：提交任务 5**

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py reports/replay/2026-06-04_A股日报_完整版_replay.md reports/replay/2026-06-05_A股日报_完整版_replay.md
git commit -m "test(report): audit bayesian diagnosis contract"
```

如果 replay 产物按项目规则不应提交，只提交代码和测试，并在最终报告里说明 replay 已生成但未纳入提交：

```bash
git add scripts/report/report_acceptance_audit.py tests/test_report_acceptance_audit.py
git commit -m "test(report): audit bayesian diagnosis contract"
```

---

## 最终验证

全部任务完成后运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_bayesian_diagnosis \
  tests.test_sniper_target_derivation \
  tests.test_front_page_v2_renderer \
  tests.test_report_acceptance_audit \
  tests.test_report_runtime

git diff --check
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-04 --replay
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

人工抽查：

- 首页有 `### 明日诊断结论`。
- 首页没有概率区间或粗概率标签。
- 附录完整路径包含 `贝叶斯诊断路径`。
- 路径包含市场、主线/板块、资金、个股、反证。
- 每层有本层判断、传给下一层、本层不能推出什么。
- 过程候选没有在后文变成最终动作。
- 2026-06-05 华电辽能做T亏损纪律没有被 50%/100% 文案覆盖。

## 自查结果

- Spec 覆盖：计划覆盖 `bayesian_diagnosis.v1`、无概率区间、旧评分证据化、同一诊断池、首页简版、推导层详版、验收检查、replay 验证。
- 占位扫描：计划没有未定占位或“之后补”类占位；每个代码步骤给出具体片段。
- 类型一致性：诊断包统一字段为 `schema_version`、`target_date`、`conclusion`、`path`、`candidate_pool`、`score_conflicts`、`counter_evidence`。
- 风险：任务 5 的 replay 产物是否提交需按项目当前规则判断；计划给出两种命令分支。
