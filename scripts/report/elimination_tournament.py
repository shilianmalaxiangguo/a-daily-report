from __future__ import annotations

import html
import json
from pathlib import Path


SCHEMA_VERSION = "elimination_tournament.v1"
SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION = "sector_capital_preflight.v1"
SECTOR_CAPITAL_PREFLIGHT_DERIVATION_CONTRACT = "sector_capital_diffusion_first.v1"

LAYER_DEFS = (
    ("sector", "板块层"),
    ("sector_role", "板块内角色层"),
    ("leader_reverse", "龙头反推层"),
    ("price_action", "价格行为层"),
    ("account_execution", "盈亏比/账户层"),
    ("final_resolution", "最终收口层"),
)

SECTOR_CAPITAL_PREFLIGHT_MERMAID = """flowchart TD
  A["第一性原理: 短期价格=资金流+筹码结构+流动性+情绪预期"] --> B["市场资金结构"]
  B --> C["板块资金扩散"]
  C --> D["板块内资金载体候选"]
  D --> E{"资金载体角色"}
  E --> E1["涨停高标: 只作证据"]
  E --> E2["趋势容量核心"]
  E --> E3["板块锚/中军"]
  E --> E4["分支龙头/量化弹性"]
  E1 --> F["量化参与痕迹"]
  E2 --> F
  E3 --> F
  E4 --> F
  F --> G["价格行为确认"]
  G --> H["周期概率窗口"]
  H --> I["反方证据"]
  I --> J["账户/盈亏比/时间窗口"]
  J --> K["唯一明日动作或不参与"]
  K --> L["白痴指数复核: 成本是否换来决策价值"]
  L --> M["压缩/合并/降级低价值高成本层"]
  M -. "下一轮优化" .-> B
"""

REQUIRED_SECTOR_CAPITAL_PREFLIGHT_MERMAID_LABELS = (
    "市场资金结构",
    "板块资金扩散",
    "量化参与痕迹",
    "价格行为确认",
    "周期概率窗口",
    "唯一明日动作或不参与",
    "白痴指数复核",
    "压缩/合并/降级低价值高成本层",
)

SECTOR_CAPITAL_PREFLIGHT_LAYER_TITLES = {
    "sector": ("sector_capital_diffusion", "板块资金扩散"),
    "sector_role": ("capital_carrier", "板块内资金载体"),
    "leader_reverse": ("carrier_role", "资金载体角色反推"),
    "price_action": ("price_action", "价格行为确认"),
    "account_execution": ("account_execution", "账户/盈亏比/时间窗口"),
    "final_resolution": ("final_action", "唯一明日动作"),
}

SECTOR_CAPITAL_PREFLIGHT_IDIOT_INDEX_REVIEW = (
    {
        "step": "涨停池起点",
        "cost_proxy": "数据多、噪音高、容易多标的",
        "decision_value": "不能解释板块为什么被资金选择",
        "idiot_index_signal": "高",
        "action": "降为证据层，不作起点",
    },
    {
        "step": "多模块各自选股",
        "cost_proxy": "token 高、冲突多、读者难复核",
        "decision_value": "容易生成多个明日标的",
        "idiot_index_signal": "高",
        "action": "合并到统一淘汰赛链路",
    },
    {
        "step": "主观分数排序",
        "cost_proxy": "看似精确、维护成本高",
        "decision_value": "不能说明真实淘汰理由",
        "idiot_index_signal": "高",
        "action": "替换为条件链和事实理由",
    },
    {
        "step": "长篇正文堆叠",
        "cost_proxy": "token 高、阅读成本高",
        "decision_value": "不能改变动作或淘汰理由",
        "idiot_index_signal": "高",
        "action": "折叠、压缩或移到附录",
    },
    {
        "step": "板块资金扩散",
        "cost_proxy": "成本中等",
        "decision_value": "决定是否有主攻方向",
        "idiot_index_signal": "低",
        "action": "保留为主链路",
    },
    {
        "step": "资金载体角色",
        "cost_proxy": "成本中等",
        "decision_value": "决定股票是否进入下一层",
        "idiot_index_signal": "低",
        "action": "保留为主链路",
    },
    {
        "step": "价格行为和反方证据",
        "cost_proxy": "成本中等",
        "decision_value": "决定参与或不参与",
        "idiot_index_signal": "低",
        "action": "保留为主链路",
    },
    {
        "step": "项目生存线复盘",
        "cost_proxy": "成本低",
        "decision_value": "判断项目是否值得继续复杂化",
        "idiot_index_signal": "低",
        "action": "每个复盘周期保留",
    },
)

CORE_ROLE_MARKERS = (
    "板块锚",
    "主线核心",
    "分支龙头",
    "大容量中军",
    "明日主买对象",
    "核心",
)

PROCESS_ONLY_ROLE_MARKERS = (
    "观察样本",
    "跟风样本",
    "过程候选",
    "低位补涨",
    "套利工具",
    "候选观察补充",
)

PASS_REVERSAL_DECISIONS = {"可作为主对象", "可作为补位"}

RISK_LAYER_ELIMINATING_LEVELS = ("高风险",)
RISK_LAYER_CAUTION_LEVELS = ("中风险",)


def clean_text(value, default=""):
    if value is None:
        return default
    text = " ".join(str(value).replace("|", "｜").split()).strip()
    return text if text else default


def clean_block_text(value, default=""):
    if value is None:
        return default
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    return text if text else default


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return list(value) if isinstance(value, list) else []


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace("%", "").strip()))
    except (TypeError, ValueError):
        return default


def normalize_stock_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def stock_payload(value):
    value = _as_dict(value)
    nested = _as_dict(value.get("stock"))
    name = clean_text(
        value.get("name")
        or value.get("stock_name")
        or value.get("名称")
        or nested.get("name")
        or nested.get("stock_name")
        or nested.get("名称")
    )
    code = normalize_stock_code(
        value.get("code")
        or value.get("stock_code")
        or value.get("代码")
        or value.get("symbol")
        or nested.get("code")
        or nested.get("stock_code")
        or nested.get("代码")
        or nested.get("symbol")
    )
    if not (name or code):
        return {}
    payload = {"name": name, "code": code}
    sector = clean_text(
        value.get("sector")
        or value.get("sector_name")
        or value.get("industry")
        or value.get("板块")
        or nested.get("sector")
        or nested.get("sector_name")
        or nested.get("industry")
        or nested.get("板块")
    )
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


def _contains_any(text, markers):
    return any(marker in text for marker in markers)


def _candidate_rows_from_workflow(selection_workflow):
    workflow = _as_dict(selection_workflow)
    rows = []
    for index, item in enumerate(_as_list(workflow.get("candidate_pool")), start=1):
        if not isinstance(item, dict):
            continue
        stock = stock_payload(item.get("stock") if isinstance(item.get("stock"), dict) else item)
        if not stock:
            continue
        row = dict(item)
        row["stock"] = stock
        row["_source_rank"] = index
        rows.append(row)
    return rows


def _trace_rows(candidate_traces):
    if isinstance(candidate_traces, dict):
        rows = candidate_traces.get("traces")
    else:
        rows = candidate_traces
    return [row for row in _as_list(rows) if isinstance(row, dict)]


def _ledger_rows(decision_ledger):
    if isinstance(decision_ledger, dict):
        rows = decision_ledger.get("cases") or decision_ledger.get("rows") or decision_ledger.get("records")
    else:
        rows = decision_ledger
    return [row for row in _as_list(rows) if isinstance(row, dict)]


def _risk_group_rows(risk_groups):
    source = _as_dict(risk_groups)
    rows = []
    for group_key, group_title in (
        ("focus_group", "明天重点候选组"),
        ("keep_group", "明天先观察组"),
        ("delete_group", "明天先回避组"),
    ):
        for row in _as_list(source.get(group_key)):
            if not isinstance(row, dict):
                continue
            enriched = dict(row)
            enriched.setdefault("_risk_group", group_key)
            enriched.setdefault("_risk_group_title", group_title)
            rows.append(enriched)
    for row in _as_list(source.get("risk_rows")):
        if isinstance(row, dict):
            rows.append(dict(row))
    return rows


def _index_by_stock(rows):
    indexed = {}
    for row in rows:
        key = stock_key(row)
        if key:
            indexed.setdefault(key, row)
    return indexed


def _risk_evidence_text(risk_row):
    risk_row = _as_dict(risk_row)
    pieces = []
    for item in _as_list(risk_row.get("risk_penalties")):
        text = clean_text(item)
        if text and text not in pieces:
            pieces.append(text)
    for key in ("reason", "tomorrow_risk", "risk_level", "dest"):
        text = clean_text(risk_row.get(key))
        if text and text not in pieces:
            pieces.append(text)
    return "；".join(pieces)


def _risk_is_eliminating(risk_row):
    risk_row = _as_dict(risk_row)
    group_key = clean_text(risk_row.get("_risk_group"))
    level = clean_text(risk_row.get("risk_level"))
    dest = clean_text(risk_row.get("dest"))
    if group_key == "delete_group":
        return True
    if _contains_any(level, RISK_LAYER_ELIMINATING_LEVELS):
        return True
    return "回避" in dest


def _risk_is_caution(risk_row):
    risk_row = _as_dict(risk_row)
    group_key = clean_text(risk_row.get("_risk_group"))
    level = clean_text(risk_row.get("risk_level"))
    dest = clean_text(risk_row.get("dest"))
    if group_key == "keep_group":
        return True
    if _contains_any(level, RISK_LAYER_CAUTION_LEVELS):
        return True
    return "观察" in dest


def _workflow_final(selection_workflow):
    final = _as_dict(_as_dict(selection_workflow).get("final"))
    target = stock_payload(final.get("execution_object"))
    pct = _safe_int(final.get("position_pct"), default=0)
    action_label = clean_text(final.get("action_text")) or _position_label(pct if target else 0)
    failure_conditions = [
        clean_text(item)
        for item in _as_list(final.get("failure_conditions"))
        if clean_text(item)
    ]
    reason = clean_text(final.get("reason") or final.get("decision_reason") or final.get("action_reason"))
    if not reason:
        if target and pct > 0:
            reason = f"最终对象={stock_label(target)}，动作={action_label}"
        else:
            reason = f"最终没有新增参与对象，动作={action_label}"
    if failure_conditions:
        reason = f"{reason}；条件未满足：" + "、".join(failure_conditions)
    return {
        "target": target if pct > 0 else {},
        "raw_target": target,
        "position_pct": pct if target and pct > 0 else 0,
        "label": action_label,
        "reason": reason,
        "source": "selection_workflow.final",
        "failure_conditions": failure_conditions,
    }


def _position_pct_from_decision(position_decision):
    decision = _as_dict(position_decision)
    for key in ("target_position_pct", "position_plan_pct", "position_pct"):
        if key in decision:
            return _safe_int(decision.get(key), default=0)
    return 0


def _position_label(position_pct):
    if position_pct >= 100:
        return "100%核心进攻"
    if position_pct >= 50:
        return "50%条件执行"
    return "0%不参与"


def _final_action_from_resolution(final_target_resolution, position_decision):
    resolution = _as_dict(final_target_resolution)
    new_entry = stock_payload(resolution.get("new_entry_target"))
    display = stock_payload(resolution.get("display_target"))
    priority = _as_dict(resolution.get("capital_priority_decision"))
    pct = _position_pct_from_decision(position_decision)
    target = new_entry if new_entry and pct > 0 else {}
    source = "final_target_resolution"
    reason = clean_text(priority.get("reason")) or "最终解析未给出新增参与对象"
    if not target:
        pct = 0
    return {
        "target": target,
        "raw_target": target or display,
        "position_pct": pct,
        "label": _position_label(pct),
        "reason": reason,
        "source": source,
        "failure_conditions": [],
    }


def _final_action(selection_workflow, final_target_resolution, position_decision):
    workflow = _as_dict(selection_workflow)
    workflow_final = _as_dict(workflow.get("final"))
    if workflow_final:
        final = _workflow_final(workflow)
        if final["position_pct"] <= 0:
            final["target"] = {}
            final["label"] = "0%不参与"
        return final
    return _final_action_from_resolution(final_target_resolution, position_decision)


def _trace_for_candidate(candidate, trace_by_key):
    return _as_dict(trace_by_key.get(stock_key(candidate)))


def _ledger_for_candidate(candidate, ledger_by_key):
    return _as_dict(ledger_by_key.get(stock_key(candidate)))


def _risk_for_candidate(candidate, risk_by_key):
    return _as_dict(risk_by_key.get(stock_key(candidate)))


def _candidate_layer_entry(candidate, *, status, reason, next_basis="", elimination_basis="", extra=None):
    stock = stock_payload(candidate.get("stock") if isinstance(candidate, dict) else candidate)
    payload = {
        "stock": stock,
        "stock_code": clean_text(stock.get("code")),
        "stock_name": clean_text(stock.get("name")),
        "stock_label": stock_label(stock),
        "status": status,
        "reason": clean_text(reason, "数据不足，无法展示本轮淘汰细节"),
        "next_basis": clean_text(next_basis),
        "elimination_basis": clean_text(elimination_basis),
        "source_pools": list(_as_list(_as_dict(candidate).get("source_pools"))),
        "sector": clean_text(_as_dict(candidate).get("sector") or stock.get("sector")),
        "sector_role": clean_text(_as_dict(candidate).get("sector_role")),
        "reversal_decision": clean_text(_as_dict(candidate).get("reversal_decision")),
    }
    for key, value in _as_dict(extra).items():
        if value not in (None, "", []):
            payload[key] = value
    return payload


def _layer_payload(layer_id, title, entries, note=""):
    entries = [_normalize_preflight_entry(entry) for entry in entries if isinstance(entry, dict)]
    input_count = len(entries)
    eliminated_count = sum(1 for item in entries if item.get("status") == "eliminated")
    survivor_count = sum(1 for item in entries if item.get("status") == "survived")
    return {
        "id": layer_id,
        "title": title,
        "input_count": input_count,
        "eliminated_count": eliminated_count,
        "survivor_count": survivor_count,
        "entries": entries,
        "survivors": [item for item in entries if item.get("status") == "survived"],
        "eliminated": [item for item in entries if item.get("status") == "eliminated"],
        "note": clean_text(note),
    }


def _normalize_preflight_entry(entry):
    entry = dict(_as_dict(entry))
    stock = stock_payload(entry.get("stock"))
    empty_final = clean_text(entry.get("status")) == "final_action" and not stock
    if not stock:
        if empty_final:
            stock = {}
        else:
            stock = {
                "code": clean_text(entry.get("stock_code") or entry.get("code")),
                "name": clean_text(entry.get("stock_name") or entry.get("name")),
                "sector": clean_text(entry.get("sector")),
            }
            stock = {key: value for key, value in stock.items() if value}
    risk_row = _as_dict(entry.pop("risk_row", None))
    if risk_row:
        risk_text = _risk_evidence_text(risk_row)
        if risk_text:
            entry["risk_evidence"] = risk_text
    entry["stock"] = stock
    entry["stock_code"] = clean_text(entry.get("stock_code") or stock.get("code"))
    entry["stock_name"] = clean_text(entry.get("stock_name") or stock.get("name"))
    if empty_final and not entry["stock_name"]:
        entry["stock_name"] = "无执行对象"
    entry["sector"] = clean_text(entry.get("sector") or stock.get("sector"))
    entry["stock_label"] = clean_text(entry.get("stock_label")) or stock_label(stock)
    entry["status"] = clean_text(entry.get("status"), "process_only")
    entry["reason"] = clean_text(entry.get("reason"), "数据不足，无法展示本层判断")
    entry["next_basis"] = clean_text(entry.get("next_basis"))
    entry["elimination_basis"] = clean_text(entry.get("elimination_basis"))
    return entry


def _normalize_preflight_layer(layer, *, layer_id="", title="", note=""):
    layer = dict(_as_dict(layer))
    if layer_id:
        layer["id"] = layer_id
    if title:
        layer["title"] = title
    if note:
        existing_note = clean_text(layer.get("note"))
        layer["note"] = "；".join(part for part in (existing_note, clean_text(note)) if part)
    entries = [_normalize_preflight_entry(entry) for entry in _as_list(layer.get("entries")) if isinstance(entry, dict)]
    layer["entries"] = entries
    layer["input_count"] = len(entries)
    layer["eliminated"] = [entry for entry in entries if entry.get("status") == "eliminated"]
    layer["survivors"] = [entry for entry in entries if entry.get("status") == "survived"]
    layer["eliminated_count"] = len(layer["eliminated"])
    layer["survivor_count"] = len(layer["survivors"])
    if "input_entries" in layer:
        layer["input_entries"] = [
            _normalize_preflight_entry(entry)
            for entry in _as_list(layer.get("input_entries"))
            if isinstance(entry, dict)
        ]
    layer["note"] = clean_text(layer.get("note"))
    return layer


def _labels_for_status(layer, status):
    labels = [
        clean_text(entry.get("stock_label"))
        for entry in _as_list(_as_dict(layer).get("entries"))
        if isinstance(entry, dict) and clean_text(entry.get("status")) == status and clean_text(entry.get("stock_label"))
    ]
    return "、".join(labels) if labels else "无"


def _first_entry_reason(layer, status):
    for entry in _as_list(_as_dict(layer).get("entries")):
        if isinstance(entry, dict) and clean_text(entry.get("status")) == status:
            return clean_text(entry.get("reason") or entry.get("elimination_basis") or entry.get("next_basis"))
    return ""


def _preflight_decision_row(*, item, conclusion, evidence, counter_evidence, tomorrow_check, action):
    return {
        "item": clean_text(item),
        "conclusion": clean_text(conclusion, "待确认"),
        "evidence": clean_text(evidence, "证据不足"),
        "counter_evidence": clean_text(counter_evidence, "暂无明确反方证据"),
        "tomorrow_check": clean_text(tomorrow_check, "次日继续验证"),
        "action": clean_text(action, "观察"),
    }


def _build_preflight_decision_list(layers, final_action):
    by_id = {clean_text(layer.get("id")): _as_dict(layer) for layer in _as_list(layers)}
    final_action = _as_dict(final_action)
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_target = stock_label(final_action.get("target")) if final_action.get("target") else "无执行对象"
    final_position = _safe_int(final_action.get("position_pct"), default=0)

    sector_layer = by_id.get("sector_capital_diffusion") or by_id.get("sector") or {}
    carrier_layer = by_id.get("capital_carrier") or by_id.get("sector_role") or {}
    role_layer = by_id.get("carrier_role") or by_id.get("leader_reverse") or {}
    price_layer = by_id.get("price_action") or {}
    account_layer = by_id.get("account_execution") or {}

    sector_survivors = _labels_for_status(sector_layer, "survived")
    carrier_survivors = _labels_for_status(carrier_layer, "survived")
    role_survivors = _labels_for_status(role_layer, "survived")
    price_survivors = _labels_for_status(price_layer, "survived")
    account_survivors = _labels_for_status(account_layer, "survived")

    if final_position > 0:
        market_action = "允许进入执行窗口"
        cycle_conclusion = "周期窗口打开"
        account_conclusion = "适配"
    else:
        market_action = "不新增参与"
        cycle_conclusion = "未打开或待确认"
        account_conclusion = "不适配或未满足"

    return [
        _preflight_decision_row(
            item="市场能否进攻",
            conclusion="可复核" if sector_layer else "证据不足",
            evidence=f"进入板块扩散层：{sector_survivors}",
            counter_evidence=_first_entry_reason(sector_layer, "eliminated") or "缺少板块扩散或市场资金结构时停止新增参与",
            tomorrow_check="次日开盘资金是否继续集中到同一板块路径",
            action=market_action,
        ),
        _preflight_decision_row(
            item="哪个板块被选择",
            conclusion=sector_survivors if sector_survivors != "无" else "空",
            evidence=f"板块扩散层剩余：{sector_survivors}",
            counter_evidence=_first_entry_reason(sector_layer, "eliminated") or clean_text(sector_layer.get("note"), "只有单点异动时降级为过程证据"),
            tomorrow_check="板块宽度、成交占比和核心承接是否继续扩散",
            action="进入资金载体层" if sector_survivors != "无" else "淘汰",
        ),
        _preflight_decision_row(
            item="谁是资金载体",
            conclusion=carrier_survivors if carrier_survivors != "无" else "空",
            evidence=f"资金载体层剩余：{carrier_survivors}；角色反推剩余：{role_survivors}",
            counter_evidence=_first_entry_reason(carrier_layer, "eliminated") or _first_entry_reason(role_layer, "eliminated") or "后排补涨或不能解释为何强于板块锚时淘汰",
            tomorrow_check="回撤是否有人接，是否仍被市场反复回看",
            action="进入价格行为层" if carrier_survivors != "无" else "淘汰",
        ),
        _preflight_decision_row(
            item="是否有量化参与痕迹",
            conclusion="待价格行为验证" if price_layer else "证据不足",
            evidence=f"可观察重心抬高、回踩承接和放量换手；价格层剩余：{price_survivors}",
            counter_evidence=_first_entry_reason(price_layer, "eliminated") or "一日脉冲、尾盘抢筹失败或跌回关键线时不新增参与",
            tomorrow_check="是否继续被买回，分歧后是否仍能横住",
            action="进入账户复核" if price_survivors != "无" else "观察",
        ),
        _preflight_decision_row(
            item="价格行为是否接受",
            conclusion="接受" if price_survivors != "无" else "不接受或待确认",
            evidence=f"价格行为层剩余：{price_survivors}",
            counter_evidence=_first_entry_reason(price_layer, "eliminated") or "炸板、高换手、跌回关键线均优先视为反方证据",
            tomorrow_check="指定窗口内是否继续站回资金成本区",
            action="参与或观察" if price_survivors != "无" else "只观察",
        ),
        _preflight_decision_row(
            item="周期概率窗口是否打开",
            conclusion=cycle_conclusion,
            evidence=f"市场、板块、资金载体和价格行为最终收口到：{final_label}",
            counter_evidence=clean_text(final_action.get("reason")) or _first_entry_reason(account_layer, "eliminated") or "周期破坏、后排掉队或价格不接受",
            tomorrow_check="是否延续同一资金路径，而不是切换到新叙事",
            action="参与" if final_position > 0 else "观察",
        ),
        _preflight_decision_row(
            item="账户是否适配",
            conclusion=account_conclusion,
            evidence=f"账户/盈亏比层剩余：{account_survivors}；最终对象：{final_target}",
            counter_evidence=_first_entry_reason(account_layer, "eliminated") or "失效线太远、窗口不清或关键数据不完整",
            tomorrow_check="买点是否靠近认错线，是否在固定时间窗口内",
            action=final_label,
        ),
    ]


def _normalize_decision_list(rows, *, layers=None, final_action=None):
    normalized = []
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        normalized.append(
            _preflight_decision_row(
                item=row.get("item") or row.get("decision_item") or row.get("决策项"),
                conclusion=row.get("conclusion") or row.get("current_conclusion") or row.get("当前结论"),
                evidence=row.get("evidence") or row.get("facts") or row.get("事实依据"),
                counter_evidence=row.get("counter_evidence") or row.get("反方证据"),
                tomorrow_check=row.get("tomorrow_check") or row.get("next_check") or row.get("明日验证"),
                action=row.get("action") or row.get("动作"),
            )
        )
    if normalized:
        return normalized
    return _build_preflight_decision_list(layers or [], final_action or {})


def _normalize_idiot_index_review(rows):
    normalized = []
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "step": clean_text(row.get("step") or row.get("环节")),
                "cost_proxy": clean_text(row.get("cost_proxy") or row.get("成本代理")),
                "decision_value": clean_text(row.get("decision_value") or row.get("决策价值")),
                "idiot_index_signal": clean_text(row.get("idiot_index_signal") or row.get("白痴指数信号")),
                "action": clean_text(row.get("action") or row.get("处理动作")),
            }
        )
    if normalized:
        return normalized
    return [dict(row) for row in SECTOR_CAPITAL_PREFLIGHT_IDIOT_INDEX_REVIEW]


def _sector_layer(candidates):
    entries = []
    survivors = []
    for candidate in candidates:
        origin = clean_text(candidate.get("candidate_origin"))
        basis = clean_text(candidate.get("entry_basis") or candidate.get("entered_reason"))
        if origin in {"sector_first", "market_emotion_line"}:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="survived",
                    reason=basis or "来自板块、资金方向或市场情绪线",
                    next_basis="进入板块内角色层",
                    extra={"candidate_origin": origin},
                )
            )
            survivors.append(candidate)
        else:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="eliminated",
                    reason=basis or "未证明来自板块发酵和市场选择",
                    elimination_basis="板块来源不足，只保留过程证据",
                    extra={"candidate_origin": origin or "unknown"},
                )
            )
    return entries, survivors


def _role_layer(candidates):
    entries = []
    survivors = []
    for candidate in candidates:
        role = clean_text(candidate.get("sector_role"))
        if role and _contains_any(role, CORE_ROLE_MARKERS) and not _contains_any(role, PROCESS_ONLY_ROLE_MARKERS):
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="survived",
                    reason=f"身份={role}",
                    next_basis="进入龙头反推层",
                )
            )
            survivors.append(candidate)
        else:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="eliminated",
                    reason=f"身份={role or '待确认'}",
                    elimination_basis="不是板块锚、主线核心或可解释的容量/分支核心",
                )
            )
    return entries, survivors


def _leader_reverse_layer(candidates):
    entries = []
    survivors = []
    for candidate in candidates:
        decision = clean_text(candidate.get("reversal_decision"))
        reason = clean_text(candidate.get("current_reason") or candidate.get("eliminated_reason"))
        if decision in PASS_REVERSAL_DECISIONS:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="survived",
                    reason=f"板块锚反推：{decision}",
                    next_basis="进入价格行为层",
                    extra={"leader_reason": reason},
                )
            )
            survivors.append(candidate)
        else:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="eliminated",
                    reason=f"板块锚反推：{decision or '待确认'}",
                    elimination_basis=reason or "不能解释为什么做它而不是板块锚",
                )
            )
    return entries, survivors


def _price_action_reason(candidate, risk_row):
    risk_text = _risk_evidence_text(risk_row)
    if risk_text:
        return risk_text
    brooks = _as_dict(candidate.get("brooks_price_action_judge"))
    parts = [
        clean_text(brooks.get("verdict")),
        clean_text(brooks.get("participation_effect")),
    ]
    return "；".join(part for part in parts if part)


def _price_action_layer(candidates, risk_by_key):
    entries = []
    survivors = []
    for candidate in candidates:
        risk_row = _risk_for_candidate(candidate, risk_by_key)
        reason = _price_action_reason(candidate, risk_row)
        brooks_status = clean_text(_as_dict(candidate.get("brooks_price_action_judge")).get("status"))
        if _risk_is_eliminating(risk_row) or brooks_status in {"risk_first", "price_rejected"}:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="eliminated",
                    reason=reason or "价格行为风险未解除",
                    elimination_basis="风险优先，明日先看竞价与承接，不新增参与",
                    extra={"risk_row": risk_row},
                )
            )
            continue
        if _risk_is_caution(risk_row) or brooks_status in {"needs_second_confirmation", "insufficient"}:
            next_basis = "风险未完全解除，进入账户和盈亏比复核"
        else:
            next_basis = "价格接受度可继续复核"
        entries.append(
            _candidate_layer_entry(
                candidate,
                status="survived",
                reason=reason or "暂无价格层淘汰证据",
                next_basis=next_basis,
                extra={"risk_row": risk_row},
            )
        )
        survivors.append(candidate)
    return entries, survivors


def _candidate_missing_data(candidate, trace_by_key, final_action):
    trace = _trace_for_candidate(candidate, trace_by_key)
    missing = [
        clean_text(item)
        for item in _as_list(trace.get("missing_data"))
        if clean_text(item)
    ]
    for item in _as_list(final_action.get("failure_conditions")):
        text = clean_text(item)
        if text and text not in missing:
            missing.append(text)
    return missing


def _account_layer(candidates, trace_by_key, ledger_by_key, final_action):
    entries = []
    survivors = []
    final_key = stock_key(final_action.get("target"))
    final_pct = _safe_int(final_action.get("position_pct"), default=0)
    for candidate in candidates:
        missing = _candidate_missing_data(candidate, trace_by_key, final_action)
        ledger = _ledger_for_candidate(candidate, ledger_by_key)
        participation = _as_dict(ledger.get("planned_participation"))
        ledger_pct = _safe_int(
            ledger.get("position_plan_pct")
            if ledger.get("position_plan_pct") is not None
            else participation.get("position_plan_pct"),
            default=0,
        )
        same_final = bool(final_key and final_key == stock_key(candidate))
        if same_final and final_pct > 0:
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="survived",
                    reason=f"最终仓位={final_pct}%",
                    next_basis="进入最终收口层",
                    extra={"ledger_position_pct": ledger_pct},
                )
            )
            survivors.append(candidate)
            continue
        reason_parts = []
        if missing:
            reason_parts.append("关键数据不完整：" + "、".join(missing))
        if ledger_pct <= 0:
            reason_parts.append("决策台账仓位=0%")
        if participation.get("action") == "skip":
            reason_parts.append("计划动作=skip")
        if final_pct <= 0:
            reason_parts.append(final_action.get("label") or "0%不参与")
        entries.append(
            _candidate_layer_entry(
                candidate,
                status="eliminated",
                reason="；".join(clean_text(item) for item in reason_parts if clean_text(item))
                or final_action.get("reason")
                or "账户、仓位或盈亏比证据不足",
                elimination_basis="不取得明日新增参与资格",
                extra={"ledger_position_pct": ledger_pct, "missing_data": missing},
            )
        )
    return entries, survivors


def _final_layer(final_action, previous_survivors):
    target = stock_payload(final_action.get("target"))
    observation = stock_payload(final_action.get("raw_target")) if not target else {}
    entry = {
        "stock": target,
        "stock_code": clean_text(target.get("code")),
        "stock_name": clean_text(target.get("name")) if target else "无执行对象",
        "sector": clean_text(target.get("sector")),
        "stock_label": stock_label(target) if target else "无执行对象",
        "status": "final_action",
        "reason": clean_text(final_action.get("reason"), "最终收口未给出新增参与对象"),
        "next_basis": "",
        "elimination_basis": "",
        "source": clean_text(final_action.get("source"), "final_target_resolution"),
        "position_pct": _safe_int(final_action.get("position_pct"), default=0),
        "action_label": clean_text(final_action.get("label"), "0%不参与"),
    }
    if observation:
        entry["observation_target"] = observation
        entry["observation_label"] = stock_label(observation)
    note = ""
    if not target:
        note = "最终没有新增参与对象；前面出现的股票只作为过程样本或观察参照。"
    elif previous_survivors and stock_key(previous_survivors[0]) != stock_key(target):
        note = "最终对象与过程样本不一致，请复核上游最终解析。"
    input_entries = [
        _candidate_layer_entry(
            candidate,
            status="survived",
            reason="上一轮晋级，进入最终动作复核",
            next_basis="最终收口层",
        )
        for candidate in previous_survivors
    ]
    return [entry], note, input_entries


def _build_candidate_indexes(candidate_traces=None, decision_ledger=None, risk_groups=None):
    return {
        "trace_by_key": _index_by_stock(_trace_rows(candidate_traces)),
        "ledger_by_key": _index_by_stock(_ledger_rows(decision_ledger)),
        "risk_by_key": _index_by_stock(_risk_group_rows(risk_groups)),
    }


def build_elimination_tournament_payload(
    *,
    trade_date="",
    variant="",
    selection_workflow=None,
    final_target_resolution=None,
    position_decision=None,
    candidate_traces=None,
    decision_ledger=None,
    risk_groups=None,
):
    workflow = _as_dict(selection_workflow)
    final_action = _final_action(workflow, final_target_resolution, position_decision)
    indexes = _build_candidate_indexes(
        candidate_traces=candidate_traces,
        decision_ledger=decision_ledger,
        risk_groups=risk_groups,
    )
    candidates = _candidate_rows_from_workflow(workflow)
    layers = []

    current = candidates
    sector_entries, current = _sector_layer(current)
    layers.append(_layer_payload("sector", "板块层", sector_entries))

    role_entries, current = _role_layer(current)
    layers.append(_layer_payload("sector_role", "板块内角色层", role_entries))

    leader_entries, current = _leader_reverse_layer(current)
    layers.append(_layer_payload("leader_reverse", "龙头反推层", leader_entries))

    price_entries, current = _price_action_layer(current, indexes["risk_by_key"])
    layers.append(_layer_payload("price_action", "价格行为层", price_entries))

    account_entries, current = _account_layer(
        current,
        indexes["trace_by_key"],
        indexes["ledger_by_key"],
        final_action,
    )
    layers.append(_layer_payload("account_execution", "盈亏比/账户层", account_entries))

    final_entries, final_note, final_input_entries = _final_layer(final_action, current)
    final_layer = _layer_payload("final_resolution", "最终收口层", final_entries, note=final_note)
    final_layer["input_count"] = len(current)
    final_layer["input_entries"] = final_input_entries
    final_layer["eliminated_count"] = 0
    final_layer["survivor_count"] = 1 if final_action.get("target") else 0
    layers.append(final_layer)

    return {
        "schema_version": SCHEMA_VERSION,
        "trade_date": clean_text(trade_date or workflow.get("target_date")),
        "variant": clean_text(variant),
        "final_action": {
            "label": clean_text(final_action.get("label"), "0%不参与"),
            "position_pct": _safe_int(final_action.get("position_pct"), default=0),
            "target": stock_payload(final_action.get("target")),
            "source": clean_text(final_action.get("source"), "final_target_resolution"),
            "reason": clean_text(final_action.get("reason")),
        },
        "candidate_count": len(candidates),
        "layers": layers,
        "elimination_summary": [
            {
                "layer_id": layer["id"],
                "layer_title": layer["title"],
                "eliminated": [entry["stock_label"] for entry in layer["eliminated"]],
                "survivors": [entry["stock_label"] for entry in layer["survivors"]],
            }
            for layer in layers
        ],
    }


def store_elimination_tournament_payload(payload, *targets):
    if not isinstance(payload, dict) or not payload:
        return {}
    stored = dict(payload)
    for target in targets:
        if isinstance(target, dict):
            target["elimination_tournament_payload"] = stored
    return stored


def _copy_preflight_layer(layer):
    layer = _as_dict(layer)
    old_id = clean_text(layer.get("id"))
    original_id = clean_text(layer.get("source_layer_id")) or old_id
    new_id, title = SECTOR_CAPITAL_PREFLIGHT_LAYER_TITLES.get(
        old_id,
        (old_id or "audit_layer", clean_text(layer.get("title"), "生成前复核层")),
    )
    copied = dict(layer)
    copied["id"] = new_id
    copied["title"] = title
    copied["source_layer_id"] = original_id
    return _normalize_preflight_layer(copied)


def _entries_for_layer(layer):
    return [
        _normalize_preflight_entry(entry)
        for entry in _as_list(_as_dict(layer).get("entries"))
        if isinstance(entry, dict)
    ]


def _build_market_capital_structure_layer(sector_layer):
    entries = []
    for entry in _entries_for_layer(sector_layer):
        status = "survived" if entry.get("status") == "survived" else "eliminated"
        reason = entry.get("reason")
        if status == "survived":
            reason = reason or "来自市场资金结构和板块扩散路径"
            next_basis = "进入板块资金扩散层"
            elimination_basis = ""
        else:
            reason = reason or "未证明来自市场资金结构选择"
            next_basis = ""
            elimination_basis = entry.get("elimination_basis") or "市场资金结构证据不足，只作过程证据"
        copied = dict(entry)
        copied.update(
            {
                "status": status,
                "reason": reason,
                "next_basis": next_basis,
                "elimination_basis": elimination_basis,
            }
        )
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "market_capital_structure",
            "title": "市场资金结构",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(sector_layer).get("source_layer_id") or _as_dict(sector_layer).get("id")),
            "note": "先判断资金是否选择了可扩散方向；涨停、热榜和旧记忆只作过程证据。",
        }
    )


def _build_quant_trace_layer(role_layer, price_layer):
    role_entries = _entries_for_layer(role_layer)
    price_entries = _entries_for_layer(price_layer)
    price_by_key = {stock_key(entry.get("stock")): entry for entry in price_entries if stock_key(entry.get("stock"))}
    entries = []
    for entry in role_entries:
        key = stock_key(entry.get("stock"))
        price_entry = price_by_key.get(key, {})
        if entry.get("status") == "survived":
            status = "survived"
            reason = "重心抬高、回踩承接和放量不崩进入价格行为复核"
            next_basis = "进入价格行为确认层"
            elimination_basis = ""
        else:
            status = "eliminated"
            reason = (
                clean_text(price_entry.get("reason"))
                or clean_text(entry.get("reason"))
                or "只是一日脉冲，未证明被资金反复回看"
            )
            next_basis = ""
            elimination_basis = (
                clean_text(price_entry.get("elimination_basis"))
                or clean_text(entry.get("elimination_basis"))
                or "量化参与痕迹不足"
            )
        copied = dict(entry)
        copied.update(
            {
                "status": status,
                "reason": reason,
                "next_basis": next_basis,
                "elimination_basis": elimination_basis,
            }
        )
        if price_entry.get("risk_evidence"):
            copied["risk_evidence"] = price_entry.get("risk_evidence")
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "quant_trace",
            "title": "量化参与痕迹",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(role_layer).get("source_layer_id") or _as_dict(role_layer).get("id")),
            "note": "只观察可见行为：重心抬高、回踩承接、放量不崩、缩量不死；不写成确定是哪类资金买入。",
        }
    )


def _build_cycle_probability_window_layer(price_layer, final_action):
    final_action = _as_dict(final_action)
    final_position = _safe_int(final_action.get("position_pct"), default=0)
    entries = []
    for entry in _entries_for_layer(price_layer):
        if entry.get("status") != "survived":
            continue
        if entry.get("status") == "survived" and final_position > 0:
            status = "survived"
            reason = "市场、板块、资金载体和价格行为同向，进入账户/盈亏比复核"
            next_basis = "进入账户/盈亏比/时间窗口"
            elimination_basis = ""
        else:
            status = "eliminated"
            reason = clean_text(entry.get("reason")) or clean_text(final_action.get("reason")) or "周期窗口未打开或待确认"
            next_basis = ""
            elimination_basis = clean_text(entry.get("elimination_basis")) or "周期未打开或价格不接受，默认回到无优势状态"
        copied = dict(entry)
        copied.update(
            {
                "status": status,
                "reason": reason,
                "next_basis": next_basis,
                "elimination_basis": elimination_basis,
            }
        )
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "cycle_probability_window",
            "title": "周期概率窗口",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(price_layer).get("source_layer_id") or _as_dict(price_layer).get("id")),
            "note": "概率窗口只作条件链合并判断，不输出精确胜率。",
        }
    )


def _build_counter_evidence_account_layer(cycle_layer, account_layer, final_action):
    final_action = _as_dict(final_action)
    account_entries = _entries_for_layer(account_layer)
    account_by_key = {stock_key(entry.get("stock")): entry for entry in account_entries if stock_key(entry.get("stock"))}
    entries = []
    for entry in _entries_for_layer(cycle_layer):
        if entry.get("status") != "survived":
            continue
        key = stock_key(entry.get("stock"))
        account_entry = account_by_key.get(key, {})
        if account_entry:
            copied = dict(account_entry)
            if entry.get("status") == "eliminated":
                copied["status"] = "eliminated"
                copied["reason"] = clean_text(entry.get("reason")) or copied.get("reason")
                copied["elimination_basis"] = clean_text(entry.get("elimination_basis")) or copied.get("elimination_basis")
            entries.append(copied)
        else:
            copied = dict(entry)
            if entry.get("status") != "survived":
                copied["reason"] = clean_text(entry.get("reason")) or clean_text(final_action.get("reason")) or "反方证据未解除"
                copied["elimination_basis"] = clean_text(entry.get("elimination_basis")) or "反方证据或账户边界未满足"
            entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "counter_evidence_account",
            "title": "反方证据与账户/盈亏比/时间窗口",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(account_layer).get("source_layer_id") or _as_dict(account_layer).get("id")),
            "note": "最后合并反方证据、失效线、账户伤害和时间窗口。",
        }
    )


def _build_sector_capital_preflight_layers(raw_layers, final_action):
    copied_layers = [_copy_preflight_layer(layer) for layer in _as_list(raw_layers) if isinstance(layer, dict)]
    by_id = {clean_text(layer.get("id")): layer for layer in copied_layers}
    sector_layer = by_id.get("sector_capital_diffusion") or {}
    carrier_layer = by_id.get("capital_carrier") or {}
    role_layer = by_id.get("carrier_role") or carrier_layer
    price_layer = by_id.get("price_action") or {}
    account_layer = by_id.get("account_execution") or {}
    final_layer = by_id.get("final_action") or {}

    market_layer = _build_market_capital_structure_layer(sector_layer)
    quant_layer = _build_quant_trace_layer(role_layer, price_layer)
    cycle_layer = _build_cycle_probability_window_layer(price_layer, final_action)
    counter_account_layer = _build_counter_evidence_account_layer(cycle_layer, account_layer, final_action)

    return [
        market_layer,
        sector_layer,
        carrier_layer,
        role_layer,
        quant_layer,
        price_layer,
        cycle_layer,
        counter_account_layer,
        final_layer,
    ]


def _normalize_source_payloads(payload=None, *, elimination_tournament_payload=None):
    payload = _as_dict(payload)
    source_bundle = payload.get("source_payloads")
    if not isinstance(source_bundle, dict) or not source_bundle:
        source_bundle = payload.get("source")
    if not isinstance(source_bundle, dict) or not source_bundle:
        if any(
            isinstance(payload.get(key), dict)
            for key in (
                "selection_workflow",
                "final_target_resolution",
                "two_layer_decision_payload",
                "sniper_target_derivation",
                "elimination_tournament_payload",
            )
        ):
            source_bundle = payload
    source_bundle = _as_dict(source_bundle)

    normalized = {
        "selection_workflow": dict(_as_dict(source_bundle.get("selection_workflow"))),
        "final_target_resolution": dict(_as_dict(source_bundle.get("final_target_resolution"))),
        "two_layer_decision_payload": dict(_as_dict(source_bundle.get("two_layer_decision_payload"))),
        "sniper_target_derivation": dict(_as_dict(source_bundle.get("sniper_target_derivation"))),
        "elimination_tournament_payload": dict(_as_dict(source_bundle.get("elimination_tournament_payload"))),
    }
    if not any(normalized.values()) and isinstance(elimination_tournament_payload, dict) and elimination_tournament_payload:
        normalized["elimination_tournament_payload"] = dict(elimination_tournament_payload)
    return normalized


def _normalize_preflight_payload(payload):
    payload = _as_dict(payload)
    if not payload:
        return {}
    normalized = dict(payload)
    normalized["schema_version"] = SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION
    normalized["derivation_contract"] = clean_text(
        normalized.get("derivation_contract"),
        SECTOR_CAPITAL_PREFLIGHT_DERIVATION_CONTRACT,
    )
    mermaid = clean_block_text(normalized.get("mermaid"))
    if not mermaid or any(label not in mermaid for label in REQUIRED_SECTOR_CAPITAL_PREFLIGHT_MERMAID_LABELS):
        mermaid = SECTOR_CAPITAL_PREFLIGHT_MERMAID
    normalized["mermaid"] = mermaid
    normalized["source_payloads"] = _normalize_source_payloads(normalized, elimination_tournament_payload=normalized.get("elimination_tournament_payload"))
    normalized.pop("source", None)
    final_action = _as_dict(normalized.get("final_action"))
    normalized["final_action"] = {
        "label": clean_text(final_action.get("label"), "0%不参与"),
        "position_pct": _safe_int(final_action.get("position_pct"), default=0),
        "target": stock_payload(final_action.get("target")),
        "source": clean_text(final_action.get("source"), "final_target_resolution"),
        "reason": clean_text(final_action.get("reason")),
    }
    if normalized["final_action"]["position_pct"] <= 0:
        normalized["final_action"]["position_pct"] = 0
        normalized["final_action"]["label"] = "0%不参与"
        normalized["final_action"]["target"] = {}
    normalized["layers"] = _build_sector_capital_preflight_layers(
        normalized.get("layers"),
        normalized.get("final_action"),
    )
    normalized["decision_list"] = _normalize_decision_list(
        normalized.get("decision_list"),
        layers=normalized.get("layers"),
        final_action=normalized.get("final_action"),
    )
    normalized["idiot_index_review"] = _normalize_idiot_index_review(normalized.get("idiot_index_review"))
    return normalized


def build_sector_capital_preflight_payload(
    *,
    trade_date="",
    variant="",
    sector_capital_preflight=None,
    source_payloads=None,
    elimination_tournament_payload=None,
):
    """Build the observational companion payload from existing final-action truth."""
    elimination = _as_dict(elimination_tournament_payload)
    final_action = dict(_as_dict(elimination.get("final_action")))
    source_payloads = _normalize_source_payloads(source_payloads, elimination_tournament_payload=elimination)
    existing = _normalize_preflight_payload(sector_capital_preflight)
    if existing:
        existing["trade_date"] = clean_text(existing.get("trade_date") or trade_date)
        existing["variant"] = clean_text(existing.get("variant") or variant or "默认")
        if source_payloads:
            existing["source_payloads"] = source_payloads
        if final_action:
            existing["final_action"] = _normalize_preflight_payload({"final_action": final_action}).get("final_action", {})
            existing["source_artifact"] = clean_text(elimination.get("schema_version"), SCHEMA_VERSION)
        return existing

    if not elimination:
        return {}
    payload = {
        "schema_version": SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION,
        "trade_date": clean_text(trade_date or elimination.get("trade_date")),
        "variant": clean_text(variant or elimination.get("variant") or "默认"),
        "derivation_contract": SECTOR_CAPITAL_PREFLIGHT_DERIVATION_CONTRACT,
        "source_artifact": clean_text(elimination.get("schema_version"), SCHEMA_VERSION),
        "source_payloads": source_payloads,
        "mermaid": SECTOR_CAPITAL_PREFLIGHT_MERMAID,
        "final_action": final_action,
        "layers": _as_list(elimination.get("layers")),
    }
    return _normalize_preflight_payload(payload)


def _html(value):
    return html.escape(clean_text(value), quote=True)


def _html_block(value):
    return html.escape(clean_block_text(value), quote=True)


def _json_for_html(payload):
    text = json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, sort_keys=True)
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("</", "<\\/")
    )


def _entry_status_label(status):
    if status == "survived":
        return "晋级下一轮"
    if status == "eliminated":
        return "本轮淘汰"
    if status == "final_action":
        return "最终动作"
    return clean_text(status, "待确认")


def _entry_class(status):
    if status == "survived":
        return "is-survived"
    if status == "eliminated":
        return "is-eliminated"
    if status == "final_action":
        return "is-final"
    return "is-pending"


def _stock_list(entries):
    labels = [clean_text(item.get("stock_label")) for item in _as_list(entries) if clean_text(item.get("stock_label"))]
    return "、".join(labels) if labels else "无"


def _stock_list_preview(entries, *, limit=3):
    labels = [clean_text(item.get("stock_label")) for item in _as_list(entries) if clean_text(item.get("stock_label"))]
    if not labels:
        return "无"
    if len(labels) <= limit:
        return "、".join(labels)
    return f"{'、'.join(labels[:limit])}等{len(labels)}只"


def _entries_with_status(entries, status):
    return [entry for entry in _as_list(entries) if isinstance(entry, dict) and entry.get("status") == status]


def _entry_meta(entry):
    parts = []
    sector = clean_text(entry.get("sector"))
    role = clean_text(entry.get("sector_role"))
    reversal = clean_text(entry.get("reversal_decision"))
    if sector:
        parts.append(f"板块：{sector}")
    if role:
        parts.append(f"身份：{role}")
    if reversal:
        parts.append(f"反推：{reversal}")
    return " ｜ ".join(parts)


def _render_input_items(layer, entries):
    layer = _as_dict(layer)
    if clean_text(layer.get("id")) in {"final_resolution", "final_action"} and _safe_int(layer.get("input_count"), 0) <= 0:
        return "<li class=\"input-chip is-empty\">无</li>"
    items = []
    for entry in _as_list(entries):
        if not isinstance(entry, dict):
            continue
        if entry.get("status") == "final_action" and not stock_payload(entry.get("stock")):
            continue
        meta = _entry_meta(entry)
        meta_html = f"<span>{_html(meta)}</span>" if meta else ""
        stock_code = stock_payload(entry.get("stock")).get("code", "")
        items.append(
            "<li class=\"input-chip candidate-card {}\" data-stock-code=\"{}\"><strong class=\"candidate-label\">{}</strong>{}</li>".format(
                _html(_entry_class(entry.get("status"))),
                _html(stock_code),
                _html(entry.get("stock_label")),
                meta_html,
            )
        )
    return "\n".join(items) if items else "<li class=\"input-chip is-empty\">无</li>"


def _render_entry_cards(entries, *, empty_text):
    cards = []
    for entry in _as_list(entries):
        if not isinstance(entry, dict):
            continue
        status = clean_text(entry.get("status"))
        status_label = _entry_status_label(status)
        meta = _entry_meta(entry)
        meta_html = f"<p class=\"stock-meta\">{_html(meta)}</p>" if meta else ""
        reason_title = "晋级依据" if status == "survived" else "淘汰原因"
        if status == "final_action":
            reason_title = "最终理由"
        reason = clean_text(entry.get("reason"), "数据不足，无法展示本轮判断细节")
        basis = clean_text(entry.get("next_basis") or entry.get("elimination_basis"))
        basis_label = "下一轮" if status == "survived" else "淘汰依据"
        if status == "final_action":
            basis = clean_text(entry.get("action_label")) or clean_text(entry.get("position_pct"))
            basis_label = "动作"
        basis_html = f"<p><b>{_html(basis_label)}：</b>{_html(basis)}</p>" if basis else ""
        stock_code = stock_payload(entry.get("stock")).get("code", "")
        cards.append(
            """
            <li class="candidate-card stock-card {klass}" data-stock-code="{stock_code}">
              <div class="stock-title">
                <strong class="candidate-label">{stock}</strong>
                <span>{status_label}</span>
              </div>
              {meta_html}
              <p class="candidate-reason"><b>{reason_title}：</b>{reason}</p>
              <div class="candidate-basis">{basis_html}</div>
            </li>
            """.format(
                klass=_html(_entry_class(status)),
                stock_code=_html(stock_code),
                stock=_html(entry.get("stock_label")),
                status_label=_html(status_label),
                meta_html=meta_html,
                reason_title=_html(reason_title),
                reason=_html(reason),
                basis_html=basis_html,
            )
        )
    if cards:
        return "\n".join(cards)
    return f"<li class=\"candidate-card stock-card is-empty\">{_html(empty_text)}</li>"


def _lane_summary_text(layer, entries, *, kind, is_final=False, output_count=0):
    if kind == "input":
        if is_final and _safe_int(layer.get("input_count"), 0) <= 0:
            return "无"
        return _stock_list_preview(entries)
    if kind == "eliminated":
        return _stock_list_preview(entries)
    if kind == "output":
        return _stock_list_preview(entries)
    return "无"


def _render_lane_details(*, title, count, lane_class, list_class, list_html, open_by_default=False):
    open_attr = " open" if open_by_default else ""
    return f"""
        <details class="lane-details {lane_class}"{open_attr}>
          <summary><span>{_html(title)}（{_html(count)}只）</span><strong>名单</strong></summary>
          <ul class="{_html(list_class)} scroll-list">
            {list_html}
          </ul>
        </details>
    """


def _entry_outcome_text(status):
    if status == "survived":
        return "晋级"
    if status == "eliminated":
        return "淘汰"
    if status == "final_action":
        return "最终动作"
    return "待确认"


def _build_key_paths(layers):
    paths = {}
    order = []
    for layer in _as_list(layers):
        layer = _as_dict(layer)
        title = clean_text(layer.get("title"))
        for entry in _as_list(layer.get("entries")):
            if not isinstance(entry, dict):
                continue
            label = clean_text(entry.get("stock_label"))
            if not label or label == "无执行对象":
                continue
            if label not in paths:
                paths[label] = []
                order.append(label)
            paths[label].append(f"{title}{_entry_outcome_text(clean_text(entry.get('status')))}")
    rendered = []
    for label in order:
        trail = paths.get(label, [])
        if len(trail) < 2:
            continue
        rendered.append(f"{label}：{' -> '.join(trail)}")
    return rendered


def _render_key_paths(layers):
    paths = _build_key_paths(layers)
    if not paths:
        return ""
    items = "\n".join(f"<li>{_html(path)}</li>" for path in paths[:8])
    return f"""
    <section class="key-paths" aria-label="关键路径">
      <div class="key-paths-head">
        <p>关键路径</p>
        <span>只展示进入过两轮以上的股票</span>
      </div>
      <ul>{items}</ul>
    </section>
    """


def _render_round(layer, *, is_final=False, round_index=1, next_title=""):
    layer = _as_dict(layer)
    entries = _as_list(layer.get("entries"))
    input_entries = _as_list(layer.get("input_entries")) if is_final else entries
    layer_id = clean_text(layer.get("id"))
    final_badge = ""
    if is_final:
        final_badge = "<span class=\"final-badge\">明日唯一动作</span>"
    note = clean_text(layer.get("note"))
    note_html = f"<p class=\"round-note\">{_html(note)}</p>" if note else ""
    missing_note = ""
    if not entries and not note:
        missing_note = "<p class=\"round-note\">数据不足，无法展示本轮淘汰细节</p>"
    survived_entries = _entries_with_status(entries, "survived")
    eliminated_entries = _entries_with_status(entries, "eliminated")
    final_entries = _entries_with_status(entries, "final_action")
    output_entries = final_entries if is_final else survived_entries
    output_title = "最终动作" if is_final else "晋级下一轮"
    output_count = _safe_int(layer.get("survivor_count"), 0)
    if is_final and final_entries:
        output_count = 1 if stock_payload(final_entries[0].get("stock")) else 0
    output_empty = "无执行对象" if is_final else "无"
    if is_final:
        round_next = f"最终动作：{_stock_list(output_entries)}"
    else:
        round_next = f"晋级至：{clean_text(next_title, '下一轮')}"
    input_count = _safe_int(layer.get("input_count"), 0)
    eliminated_count = _safe_int(layer.get("eliminated_count"), 0)
    input_summary = _lane_summary_text(layer, input_entries, kind="input", is_final=is_final)
    eliminated_summary = _lane_summary_text(layer, eliminated_entries, kind="eliminated")
    output_summary = _lane_summary_text(layer, output_entries, kind="output")
    input_open = input_count <= 3
    eliminated_open = eliminated_count <= 3
    return f"""
    <section class="tournament-round round-card" id="layer-{_html(layer_id)}" data-layer-id="{_html(layer_id)}" data-round-index="{_html(round_index)}">
      <div class="round-head">
        <div>
          <p class="round-id">{_html(layer_id)}</p>
          <h2>第{_html(round_index)}轮：{_html(layer.get("title"))}{final_badge}</h2>
          <p class="round-next">{_html(round_next)}</p>
        </div>
        <dl class="round-counts">
          <div><dt>本轮输入</dt><dd>{_html(layer.get("input_count"))}</dd></div>
          <div><dt>本轮淘汰</dt><dd>{_html(layer.get("eliminated_count"))}</dd></div>
          <div><dt>{_html("最终动作" if is_final else "本轮晋级")}</dt><dd>{_html(output_count)}</dd></div>
        </dl>
      </div>
      {note_html}
      {missing_note}
      <div class="round-brief">
        <p><strong>本轮输入 {_html(layer.get("input_count"))} 只：</strong>{_html(input_summary)}</p>
        <p><strong>本轮淘汰 {_html(layer.get("eliminated_count"))} 只：</strong>{_html(eliminated_summary)}</p>
        <p><strong>{_html("最终动作" if is_final else "本轮晋级")} {_html(output_count)} 只：</strong>{_html(output_summary)}</p>
      </div>
      <div class="round-lanes" aria-label="{_html(layer.get("title"))} 淘汰赛名单">
        {_render_lane_details(title="本轮输入", count=input_count, lane_class="round-lane input-lane round-inputs", list_class="input-list", list_html=_render_input_items(layer, input_entries), open_by_default=input_open)}
        {_render_lane_details(title="本轮淘汰", count=eliminated_count, lane_class="round-lane eliminated-lane round-eliminated", list_class="stock-list", list_html=_render_entry_cards(eliminated_entries, empty_text="本轮没有淘汰"), open_by_default=eliminated_open)}
        {_render_lane_details(title="最终动作" if is_final else "本轮晋级", count=output_count, lane_class="round-lane survived-lane round-survivors", list_class="stock-list", list_html=_render_entry_cards(output_entries, empty_text=output_empty), open_by_default=True)}
      </div>
    </section>
    """


def render_elimination_tournament_html(payload):
    payload = payload if isinstance(payload, dict) else {}
    final_action = _as_dict(payload.get("final_action"))
    layers = _as_list(payload.get("layers"))
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_stock = stock_label(final_action.get("target")) if final_action.get("target") else "无执行对象"
    rendered_layers = []
    for index, layer in enumerate(layers):
        next_layer = _as_dict(layers[index + 1]) if index + 1 < len(layers) else {}
        rendered_layers.append(
            _render_round(
                layer,
                is_final=index == len(layers) - 1,
                round_index=index + 1,
                next_title=clean_text(next_layer.get("title")),
            )
        )
    if not rendered_layers:
        rendered_layers.append(
            _render_round(
                {
                    "id": "missing",
                    "title": "数据不足",
                    "input_count": 0,
                    "eliminated_count": 0,
                    "survivor_count": 0,
                    "entries": [],
                    "note": "数据不足，无法展示本轮淘汰细节",
                },
                is_final=True,
                round_index=1,
            )
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="artifact" content="elimination-tournament">
  <title>{_html(payload.get("trade_date"))} 明日标的选股淘汰赛</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --panel: #ffffff;
      --page: #f5f7fb;
      --survived: #0f766e;
      --survived-bg: #e8f6f3;
      --eliminated: #b42318;
      --eliminated-bg: #fff1f0;
      --final: #7a4d00;
      --final-bg: #fff7df;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.55;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 44px;
    }}
    header {{
      margin-bottom: 18px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
	    .final-summary {{
	      display: grid;
	      grid-template-columns: repeat(4, minmax(0, 1fr));
	      gap: 10px;
	      margin: 18px 0 22px;
	    }}
	    .tournament-flow {{
	      margin-top: 8px;
	    }}
    .summary-cell {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }}
    .summary-cell span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
	    .summary-cell strong {{
	      display: block;
	      font-size: 16px;
	      overflow-wrap: anywhere;
	    }}
	    .key-paths {{
	      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin: 0 0 18px;
	      padding: 14px 16px;
	    }}
	    .key-paths-head {{
	      display: flex;
	      align-items: baseline;
	      justify-content: space-between;
	      gap: 16px;
	      margin-bottom: 8px;
	    }}
	    .key-paths-head p {{
	      margin: 0;
	      font-size: 15px;
	      font-weight: 700;
	    }}
	    .key-paths-head span {{
	      color: var(--muted);
	      font-size: 12px;
	    }}
	    .key-paths ul {{
	      display: grid;
	      gap: 6px;
	      list-style: none;
	      margin: 0;
	      padding: 0;
	    }}
	    .key-paths li {{
	      border: 1px solid #c8d8ec;
	      border-radius: 8px;
	      background: #f7fbff;
	      padding: 8px 10px;
	      font-size: 13px;
	      overflow-wrap: anywhere;
	    }}
		    .round-card {{
		      position: relative;
		      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin-top: 18px;
	      overflow: hidden;
	    }}
	    .round-card + .round-card::before {{
	      content: "";
	      position: absolute;
	      top: -18px;
	      left: 34px;
	      width: 2px;
	      height: 18px;
	      background: var(--line);
	    }}
	    .round-head {{
	      display: flex;
	      justify-content: space-between;
	      gap: 16px;
	      padding: 16px 16px 12px;
	      border-bottom: 1px solid var(--line);
	      background: #fafbfe;
	    }}
	    .round-id {{
	      margin: 0 0 4px;
	      color: var(--muted);
	      font-size: 12px;
	      text-transform: uppercase;
	    }}
	    h2 {{
	      margin: 0;
	      font-size: 20px;
	      letter-spacing: 0;
	    }}
	    .round-next {{
	      margin: 6px 0 0;
	      color: var(--muted);
	      font-size: 13px;
	    }}
	    .final-badge {{
	      display: inline-block;
	      margin-left: 8px;
      padding: 2px 7px;
      border-radius: 999px;
      background: var(--final-bg);
      color: var(--final);
      font-size: 12px;
      vertical-align: middle;
    }}
	    .round-counts {{
	      display: grid;
	      grid-template-columns: repeat(3, 74px);
	      gap: 8px;
	      margin: 0;
	    }}
	    .round-counts div {{
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 7px 8px;
	      text-align: center;
	      background: #fff;
	    }}
	    .round-counts dt {{
	      color: var(--muted);
	      font-size: 12px;
	    }}
	    .round-counts dd {{
	      margin: 0;
	      font-size: 18px;
	      font-weight: 700;
	    }}
	    .round-note,
	    .round-brief {{
	      margin: 12px 16px;
	      color: var(--muted);
	      font-size: 13px;
	    }}
	    .round-brief p {{
	      margin: 4px 0;
	    }}
	    .round-lanes {{
	      display: grid;
	      grid-template-columns: minmax(0, 1fr) minmax(0, 1.08fr) minmax(0, 1.08fr);
	      gap: 12px;
	      padding: 0 16px 16px;
	    }}
		    .round-lane {{
		      border: 1px solid var(--line);
		      border-radius: 8px;
		      background: #fff;
		      min-width: 0;
		    }}
	    .lane-details {{
	      overflow: hidden;
	    }}
	    .lane-details summary {{
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 8px;
	      min-height: 44px;
	      padding: 10px 12px;
	      border-bottom: 1px solid var(--line);
	      cursor: pointer;
	      font-size: 14px;
	      font-weight: 700;
	      list-style: none;
	    }}
	    .lane-details summary::-webkit-details-marker {{
	      display: none;
	    }}
	    .lane-details summary::before {{
	      content: "›";
	      display: inline-flex;
	      align-items: center;
	      justify-content: center;
	      width: 18px;
	      height: 18px;
	      margin-right: 6px;
	      color: var(--muted);
	      transform: rotate(0deg);
	      transition: transform 160ms cubic-bezier(0.2, 0.8, 0.2, 1);
	    }}
	    .lane-details[open] summary::before {{
	      transform: rotate(90deg);
	    }}
	    .lane-details summary span {{
	      display: inline-flex;
	      align-items: center;
	      flex: 1 1 auto;
	    }}
	    .lane-details summary strong {{
	      color: var(--muted);
	      font-size: 12px;
	    }}
	    .scroll-list {{
	      max-height: 260px;
	      overflow-y: auto;
	      overscroll-behavior: contain;
	    }}
		    .input-list,
		    .stock-list {{
	      list-style: none;
	      margin: 0;
	      padding: 10px;
	    }}
	    .input-list {{
	      display: flex;
	      flex-wrap: wrap;
	      gap: 8px;
	      align-content: flex-start;
	    }}
	    .input-chip {{
	      display: inline-flex;
	      flex-direction: column;
	      max-width: 100%;
	      gap: 2px;
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 7px 9px;
	      background: #f8fafc;
	      overflow-wrap: anywhere;
	    }}
	    .input-chip strong {{
	      font-size: 13px;
	    }}
	    .input-chip span {{
	      color: var(--muted);
	      font-size: 11px;
	    }}
	    .stock-card {{
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 10px;
	      margin-bottom: 8px;
	      overflow-wrap: anywhere;
	    }}
	    .stock-card:last-child {{
	      margin-bottom: 0;
	    }}
	    .stock-title {{
	      display: flex;
	      justify-content: space-between;
	      gap: 8px;
	      align-items: flex-start;
	    }}
	    .stock-title strong {{
	      font-size: 14px;
	    }}
	    .stock-title span {{
	      flex: 0 0 auto;
	      border-radius: 999px;
	      padding: 2px 7px;
	      font-size: 12px;
	      font-weight: 700;
	    }}
	    .stock-card p {{
	      margin: 7px 0 0;
	      font-size: 13px;
	    }}
	    .stock-meta {{
	      color: var(--muted);
	    }}
	    .is-survived {{
	      border-color: #99d6ce;
	      background: var(--survived-bg);
	    }}
	    .is-survived .stock-title span {{
	      color: var(--survived);
	      background: #d8f1ed;
	    }}
	    .is-eliminated {{
	      border-color: #f5b5ae;
	      background: var(--eliminated-bg);
	    }}
	    .is-eliminated .stock-title span {{
	      color: var(--eliminated);
	      background: #ffe0dc;
	    }}
	    .is-final {{
	      border-color: #e6c15c;
	      background: var(--final-bg);
	    }}
	    .is-final .stock-title span {{
	      color: var(--final);
	      background: #ffedb8;
	    }}
	    .is-empty {{
	      color: var(--muted);
	      background: #f8fafc;
	    }}
		    @media (max-width: 760px) {{
		      main {{ padding: 20px 12px 32px; }}
		      .final-summary {{ grid-template-columns: 1fr 1fr; }}
		      .key-paths-head {{ display: block; }}
		      .round-head {{ display: block; }}
		      .round-counts {{ grid-template-columns: repeat(3, 1fr); margin-top: 12px; }}
		      .round-lanes {{ grid-template-columns: 1fr; }}
	    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{_html(payload.get("trade_date"))} 明日标的选股淘汰赛</h1>
      <p class="subtitle">从板块到最终动作逐层复核；非最终层只展示过程证据，不生成新的明日标的。</p>
    </header>
	    <section class="final-summary final-action-summary" aria-label="最终动作摘要">
      <div class="summary-cell"><span>日期</span><strong>{_html(payload.get("trade_date"))}</strong></div>
      <div class="summary-cell"><span>模式</span><strong>{_html(payload.get("variant") or "默认")}</strong></div>
      <div class="summary-cell"><span>最终对象</span><strong>{_html(final_stock)}</strong></div>
      <div class="summary-cell"><span>最终动作</span><strong>{_html(final_label)}</strong></div>
	    </section>
	    {_render_key_paths(layers)}
		    <section class="tournament-flow" aria-label="选股淘汰赛流程">
		      {"".join(rendered_layers)}
		    </section>
  </main>
  <script type="application/json" id="elimination-payload">{_json_for_html(payload)}</script>
</body>
</html>
"""


def _render_preflight_layer(layer, *, round_index=1):
    layer = _as_dict(layer)
    entries = _as_list(layer.get("entries"))
    layer_id = clean_text(layer.get("id"))
    is_final = layer_id == "final_action"
    input_entries = _as_list(layer.get("input_entries")) if is_final else entries
    note = clean_text(layer.get("note"))
    note_html = f"<p class=\"round-note\">{_html(note)}</p>" if note else ""
    if not entries and not input_entries and not note:
        note_html = "<p class=\"round-note\">数据不足，无法展示本层复核细节</p>"
    input_count = _safe_int(layer.get("input_count"), 0)
    eliminated_count = _safe_int(layer.get("eliminated_count"), 0)
    survivor_count = _safe_int(layer.get("survivor_count"), 0)
    input_summary = _lane_summary_text(layer, input_entries, kind="input", is_final=is_final)
    eliminated_summary = _lane_summary_text(layer, _entries_with_status(entries, "eliminated"), kind="eliminated")
    survivor_summary = _lane_summary_text(layer, _entries_with_status(entries, "survived"), kind="output")
    if is_final:
        survivor_summary = _lane_summary_text(layer, _entries_with_status(entries, "final_action"), kind="output")
    return f"""
    <section class="tournament-round round-card preflight-layer" id="preflight-layer-{_html(layer_id)}" data-layer-id="{_html(layer_id)}" data-round-index="{_html(round_index)}">
      <div class="round-head">
        <div>
          <p class="round-id">{_html(layer_id)}</p>
          <h2>第{_html(round_index)}层：{_html(layer.get("title"))}</h2>
          <p class="round-next">生成前复核层，只解释条件链，不产生第二个明日对象</p>
        </div>
        <dl class="round-counts">
          <div><dt>本层输入</dt><dd>{_html(input_count)}</dd></div>
          <div><dt>本层淘汰</dt><dd>{_html(eliminated_count)}</dd></div>
          <div><dt>本层剩余</dt><dd>{_html(survivor_count)}</dd></div>
        </dl>
      </div>
      {note_html}
      <div class="round-brief">
        <p><strong>本层输入 {_html(input_count)} 只：</strong>{_html(input_summary)}</p>
        <p><strong>本层淘汰 {_html(eliminated_count)} 只：</strong>{_html(eliminated_summary)}</p>
        <p><strong>本层剩余 {_html(survivor_count)} 只：</strong>{_html(survivor_summary)}</p>
      </div>
      <div class="round-lanes">
        {_render_lane_details(title="本层输入", count=input_count, lane_class="round-lane input-lane round-inputs", list_class="input-list", list_html=_render_input_items(layer, input_entries), open_by_default=input_count <= 3)}
        {_render_lane_details(title="本层淘汰", count=eliminated_count, lane_class="round-lane eliminated-lane round-eliminated", list_class="stock-list", list_html=_render_entry_cards(_entries_with_status(entries, "eliminated"), empty_text="本层没有淘汰"), open_by_default=eliminated_count <= 3)}
        {_render_lane_details(title="本层剩余", count=survivor_count, lane_class="round-lane survived-lane round-survivors", list_class="stock-list", list_html=_render_entry_cards(_entries_with_status(entries, "final_action") or _entries_with_status(entries, "survived"), empty_text="无"), open_by_default=True)}
      </div>
    </section>
    """


def _render_preflight_table(*, title, summary, columns, rows, row_class=""):
    header = "".join(f"<th>{_html(label)}</th>" for _, label in columns)
    body_rows = []
    for row in _as_list(rows):
        if not isinstance(row, dict):
            continue
        cells = "".join(f"<td>{_html(row.get(key))}</td>" for key, _ in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    if not body_rows:
        body_rows.append(
            "<tr><td colspan=\"{}\">{}</td></tr>".format(
                len(columns),
                _html("暂无可展示内容"),
            )
        )
    return f"""
    <details class="audit-table-block {row_class}" open>
      <summary>
        <span>{_html(title)}</span>
        <strong>{_html(summary)}</strong>
      </summary>
      <div class="table-scroll">
        <table>
          <thead><tr>{header}</tr></thead>
          <tbody>{"".join(body_rows)}</tbody>
        </table>
      </div>
    </details>
    """


def _render_preflight_decision_list(rows):
    return _render_preflight_table(
        title="相关决策列表",
        summary="每个关键结论来自哪一层事实",
        row_class="decision-list-block",
        columns=(
            ("item", "决策项"),
            ("conclusion", "当前结论"),
            ("evidence", "事实依据"),
            ("counter_evidence", "反方证据"),
            ("tomorrow_check", "明日验证"),
            ("action", "动作"),
        ),
        rows=rows,
    )


def _render_preflight_idiot_index_review(rows):
    return _render_preflight_table(
        title="白痴指数复核表",
        summary="只判断流程效率，不参与选股",
        row_class="idiot-index-block",
        columns=(
            ("step", "环节"),
            ("cost_proxy", "成本代理"),
            ("decision_value", "决策价值"),
            ("idiot_index_signal", "白痴指数信号"),
            ("action", "处理动作"),
        ),
        rows=rows,
    )


def render_sector_capital_preflight_html(payload):
    payload = _normalize_preflight_payload(payload)
    final_action = _as_dict(payload.get("final_action"))
    layers = _as_list(payload.get("layers"))
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_stock = stock_label(final_action.get("target")) if final_action.get("target") else "无执行对象"
    rendered_layers = "\n".join(
        _render_preflight_layer(layer, round_index=index)
        for index, layer in enumerate(layers, start=1)
    )
    if not rendered_layers:
        rendered_layers = _render_preflight_layer(
            {
                "id": "missing",
                "title": "数据不足",
                "input_count": 0,
                "eliminated_count": 0,
                "survivor_count": 0,
                "entries": [],
                "note": "数据不足，无法展示生成前复核细节",
            },
            round_index=1,
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="artifact" content="sector-capital-preflight">
  <title>{_html(payload.get("trade_date"))} 板块资金扩散生成前复核</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #667085;
      --line: #d8dee8;
      --panel: #ffffff;
      --page: #f5f7fb;
      --survived: #0f766e;
      --survived-bg: #e8f6f3;
      --eliminated: #b42318;
      --eliminated-bg: #fff1f0;
      --final: #7a4d00;
      --final-bg: #fff7df;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--page);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.55;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 44px;
    }}
    header {{
      margin-bottom: 18px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .final-summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 18px 0 22px;
    }}
    .summary-cell {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }}
    .summary-cell span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .summary-cell strong {{
      display: block;
      font-size: 16px;
      overflow-wrap: anywhere;
    }}
    .mermaid-block {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 18px;
    }}
    .mermaid-block h2 {{
      margin: 0 0 8px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .mermaid-block pre {{
      margin: 0;
      overflow-x: auto;
      white-space: pre;
      font-size: 13px;
      line-height: 1.5;
    }}
    .audit-table-block {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 0 0 18px;
      overflow: hidden;
    }}
    .audit-table-block summary {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 46px;
      padding: 12px 16px;
      cursor: pointer;
      font-weight: 700;
      list-style: none;
      background: #fafbfe;
      border-bottom: 1px solid var(--line);
    }}
    .audit-table-block summary::-webkit-details-marker {{
      display: none;
    }}
    .audit-table-block summary strong {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
      text-align: right;
    }}
    .table-scroll {{
      max-height: 300px;
      overflow: auto;
    }}
    table {{
      width: 100%;
      min-width: 920px;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th,
    td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
    }}
    .round-card {{
      position: relative;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 18px;
      overflow: hidden;
    }}
    .round-card + .round-card::before {{
      content: "";
      position: absolute;
      top: -18px;
      left: 34px;
      width: 2px;
      height: 18px;
      background: var(--line);
    }}
    .round-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 16px 12px;
      border-bottom: 1px solid var(--line);
      background: #fafbfe;
    }}
    .round-id {{
      margin: 0 0 4px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: 0;
    }}
    .round-next {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .round-counts {{
      display: grid;
      grid-template-columns: repeat(3, 74px);
      gap: 8px;
      margin: 0;
    }}
    .round-counts div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 7px 8px;
      text-align: center;
      background: #fff;
    }}
    .round-counts dt {{
      color: var(--muted);
      font-size: 12px;
    }}
    .round-counts dd {{
      margin: 0;
      font-size: 18px;
      font-weight: 700;
    }}
    .round-note,
    .round-brief {{
      margin: 12px 16px;
      color: var(--muted);
      font-size: 13px;
    }}
    .round-brief p {{
      margin: 4px 0;
    }}
    .round-lanes {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.08fr) minmax(0, 1.08fr);
      gap: 12px;
      padding: 0 16px 16px;
    }}
    .round-lane {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      min-width: 0;
    }}
    .lane-details {{
      overflow: hidden;
    }}
    .lane-details summary {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 44px;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      cursor: pointer;
      font-size: 14px;
      font-weight: 700;
      list-style: none;
    }}
    .lane-details summary::-webkit-details-marker {{
      display: none;
    }}
    .scroll-list {{
      max-height: 260px;
      overflow-y: auto;
      overscroll-behavior: contain;
    }}
    .input-list,
    .stock-list {{
      list-style: none;
      margin: 0;
      padding: 10px;
    }}
    .input-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-content: flex-start;
    }}
    .input-chip {{
      display: inline-flex;
      flex-direction: column;
      max-width: 100%;
      gap: 2px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 7px 9px;
      background: #f8fafc;
      overflow-wrap: anywhere;
    }}
    .input-chip strong {{
      font-size: 13px;
    }}
    .input-chip span {{
      color: var(--muted);
      font-size: 11px;
    }}
    .stock-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      overflow-wrap: anywhere;
    }}
    .stock-card:last-child {{
      margin-bottom: 0;
    }}
    .stock-title {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: flex-start;
    }}
    .stock-title strong {{
      font-size: 14px;
    }}
    .stock-title span {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 2px 7px;
      font-size: 12px;
      font-weight: 700;
    }}
    .stock-card p {{
      margin: 7px 0 0;
      font-size: 13px;
    }}
    .stock-meta {{
      color: var(--muted);
    }}
    .is-survived {{
      border-color: #99d6ce;
      background: var(--survived-bg);
    }}
    .is-survived .stock-title span {{
      color: var(--survived);
      background: #d8f1ed;
    }}
    .is-eliminated {{
      border-color: #f5b5ae;
      background: var(--eliminated-bg);
    }}
    .is-eliminated .stock-title span {{
      color: var(--eliminated);
      background: #ffe0dc;
    }}
    .is-final {{
      border-color: #e6c15c;
      background: var(--final-bg);
    }}
    .is-final .stock-title span {{
      color: var(--final);
      background: #ffedb8;
    }}
    .is-empty {{
      color: var(--muted);
      background: #f8fafc;
    }}
    @media (max-width: 760px) {{
      main {{ padding: 20px 12px 32px; }}
      .final-summary {{ grid-template-columns: 1fr 1fr; }}
      .audit-table-block summary {{ display: block; }}
      .audit-table-block summary strong {{ display: block; margin-top: 4px; text-align: left; }}
      .round-head {{ display: block; }}
      .round-counts {{ grid-template-columns: repeat(3, 1fr); margin-top: 12px; }}
      .round-lanes {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{_html(payload.get("trade_date"))} 板块资金扩散生成前复核</h1>
      <p class="subtitle">从市场资金结构、板块扩散、资金载体到唯一明日动作逐层复核；本页只解释条件链，不生成新的明日对象。</p>
    </header>
    <section class="final-summary final-action-summary" aria-label="最终动作摘要">
      <div class="summary-cell"><span>日期</span><strong>{_html(payload.get("trade_date"))}</strong></div>
      <div class="summary-cell"><span>模式</span><strong>{_html(payload.get("variant") or "默认")}</strong></div>
      <div class="summary-cell"><span>最终对象</span><strong>{_html(final_stock)}</strong></div>
      <div class="summary-cell"><span>最终动作</span><strong>{_html(final_label)}</strong></div>
    </section>
    <section class="mermaid-block" aria-label="生成前复核流程">
      <h2>生成前复核流程</h2>
      <pre><code>{_html_block(payload.get("mermaid"))}</code></pre>
    </section>
    {_render_preflight_decision_list(payload.get("decision_list"))}
    {_render_preflight_idiot_index_review(payload.get("idiot_index_review"))}
    <section class="tournament-flow" aria-label="板块资金扩散生成前复核层">
      {rendered_layers}
    </section>
  </main>
  <script type="application/json" id="sector-capital-preflight-payload">{_json_for_html(payload)}</script>
</body>
</html>
"""


def elimination_tournament_html_path(markdown_path, trade_date):
    base = Path(markdown_path).parent if markdown_path else Path("reports")
    return base / f"{clean_text(trade_date)}_明日标的选股淘汰赛.html"


def sector_capital_preflight_html_path(markdown_path, trade_date):
    base = Path(markdown_path).parent if markdown_path else Path("reports")
    return base / f"{clean_text(trade_date)}_板块资金扩散生成前复核.html"


def save_elimination_tournament_html(payload, markdown_path, *, trade_date=""):
    path = elimination_tournament_html_path(markdown_path, trade_date or _as_dict(payload).get("trade_date"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_elimination_tournament_html(payload), encoding="utf-8")
    return path


def save_sector_capital_preflight_html(payload, markdown_path, *, trade_date=""):
    payload = _normalize_preflight_payload(payload)
    path = sector_capital_preflight_html_path(markdown_path, trade_date or _as_dict(payload).get("trade_date"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sector_capital_preflight_html(payload), encoding="utf-8")
    return path
