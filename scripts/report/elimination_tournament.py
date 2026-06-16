from __future__ import annotations

import html
import json
import re
import datetime as _dt
from pathlib import Path


SCHEMA_VERSION = "elimination_tournament.v1"
SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION = "sector_capital_preflight.v1"
SECTOR_CAPITAL_PREFLIGHT_DERIVATION_CONTRACT = "sector_capital_diffusion_first.v1"
TPLUS_REHEARSAL_SCHEMA_VERSION = "t0_tplus_rehearsal.v1"

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
  G --> H["周期窗口"]
  H --> I["反方证据"]
  I --> J["账户/盈亏比/时间窗口"]
  J --> K["唯一明日动作或不参与"]
  K --> L["T+1参与预案: 参与窗口/确认/取消"]
  L --> M["T+2情绪周期推演: 市场/板块/卖出处理"]
  M --> N["后验复盘: 只批改不回写T0"]
  N --> O["白痴指数复核: 成本是否换来决策价值"]
  O --> P["压缩/合并/降级低价值高成本层"]
  P -. "下一轮优化" .-> B
"""

LOCAL_MERMAID_RENDERER_SCRIPT = """
  <script>
    (function() {
      const nodes = Array.from(document.querySelectorAll('.mermaid'));
      if (!nodes.length) return;

      const escapeText = (value) => String(value || '').replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char]));

      const wrapLabel = (label) => {
        const text = String(label || '').trim();
        if (!text) return [''];
        if (text.length <= 18) return [text];
        const lines = [];
        let rest = text;
        while (rest.length > 18 && lines.length < 3) {
          let cut = rest.lastIndexOf(' ', 18);
          if (cut < 8) cut = 18;
          lines.push(rest.slice(0, cut));
          rest = rest.slice(cut).trim();
        }
        if (rest) lines.push(rest.length > 22 ? `${rest.slice(0, 21)}...` : rest);
        return lines.slice(0, 4);
      };

      const extractNodes = (source) => {
        const labels = new Map();
        const order = [];
        const pattern = /([A-Za-z][A-Za-z0-9_-]*)\\s*(?:\\[\\s*"([^"]+)"\\s*\\]|\\{\\s*"([^"]+)"\\s*\\})/g;
        let match;
        while ((match = pattern.exec(source)) !== null) {
          const id = match[1];
          const label = (match[2] || match[3] || id).trim();
          if (!labels.has(id)) {
            labels.set(id, label);
            order.push(id);
          }
        }
        return order.map((id) => ({ id, label: labels.get(id) || id }));
      };

      const renderLocalSvg = (node) => {
        const graphNodes = extractNodes(node.textContent || '');
        if (!graphNodes.length) {
          node.setAttribute('data-mermaid-status', 'empty');
          return;
        }
        const boxWidth = 230;
        const boxHeight = 86;
        const gap = 42;
        const pad = 18;
        const width = Math.max(320, pad * 2 + graphNodes.length * boxWidth + Math.max(0, graphNodes.length - 1) * gap);
        const height = pad * 2 + boxHeight;
        const boxes = graphNodes.map((item, index) => {
          const x = pad + index * (boxWidth + gap);
          const y = pad;
          const lines = wrapLabel(item.label);
          const text = lines.map((line, lineIndex) => {
            const dy = 34 + lineIndex * 18;
            return `<text x="${x + boxWidth / 2}" y="${y + dy}" text-anchor="middle" font-size="13" fill="#172033">${escapeText(line)}</text>`;
          }).join('');
          return `
            <g>
              <rect x="${x}" y="${y}" width="${boxWidth}" height="${boxHeight}" rx="8" fill="#ffffff" stroke="#d8dee8"></rect>
              ${text}
            </g>
          `;
        }).join('');
        const arrows = graphNodes.slice(0, -1).map((_, index) => {
          const x1 = pad + index * (boxWidth + gap) + boxWidth;
          const x2 = x1 + gap - 8;
          const y = pad + boxHeight / 2;
          return `<line x1="${x1 + 8}" y1="${y}" x2="${x2}" y2="${y}" stroke="#667085" stroke-width="1.6" marker-end="url(#arrow)"></line>`;
        }).join('');
        node.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Mermaid flowchart">
            <defs>
              <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <path d="M0,0 L8,4 L0,8 z" fill="#667085"></path>
              </marker>
            </defs>
            ${arrows}
            ${boxes}
          </svg>
        `;
        node.setAttribute('data-mermaid-status', 'local-svg');
      };

      nodes.forEach(renderLocalSvg);
    })();
  </script>
"""

REQUIRED_SECTOR_CAPITAL_PREFLIGHT_MERMAID_LABELS = (
    "市场资金结构",
    "板块资金扩散",
    "量化参与痕迹",
    "价格行为确认",
    "周期窗口",
    "唯一明日动作或不参与",
    "T+1参与预案",
    "T+2情绪周期推演",
    "只批改不回写T0",
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

LEGACY_SIGNAL_ONLY_REASON = "涨停、连板、T字板、一字板、热榜或旧龙头记忆只能作为过程证据，不能作为新仓入口"

SECTOR_CAPITAL_PREFLIGHT_LAYER_ORDER = (
    "market_capital_structure",
    "sector_capital_diffusion",
    "capital_carrier",
    "carrier_role",
    "quant_trace",
    "price_action",
    "cycle_window",
    "counter_evidence_account",
    "final_action",
)

SECTOR_CAPITAL_PREFLIGHT_DAILY_CONTEXT_KEYS = (
    "hot_rank_top30",
    "hot_rank_top50",
    "integrated_hot_list",
    "hot_plates",
    "zt_pool",
    "zt_pool_by_sector",
    "lianban_data",
    "sector_fund_flow",
    "sector_attack_evidence_rows",
    "current_mainline_history_record",
    "current_sector_turnover_snapshot",
    "crossline_observation_stocks",
    "watch_anchor",
    "special_probe_verdict",
    "tracking_memory_status",
    "recent_extreme_conviction_mentions",
    "recent_extreme_conviction_mentions_for_review",
)

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

TREND_SECOND_WAVE_MARKERS = (
    "趋势龙头",
    "趋势容量",
    "容量核心",
    "二波",
    "趋势比价链",
    "大容量趋势龙头",
    "趋势审美",
    "高低点上移",
    "MA20",
    "20日区间位置健康",
    "平台呼吸",
    "蛇形走位",
    "放量冲高",
    "新异动待观察",
    "跌不下去",
    "主线内核",
    "板块锚定龙",
    "hot_capacity_anchor_source",
    "anchor_reversal_source",
    "core_transmitter",
    "trend_chain_anchor",
    "middle_transmitter",
)

RISK_LAYER_ELIMINATING_LEVELS = ("高风险",)
RISK_LAYER_CAUTION_LEVELS = ("中风险",)
PRICE_ACTION_REJECT_MARKERS = (
    "价格行为证据不足",
    "不新增资格",
    "价格不接受",
    "价格行为风险未解除",
    "风险优先",
)
PRICE_ACTION_ACCEPT_MARKERS = (
    "资金表态被价格接受",
    "价格行为未见明确破坏",
    "价格接受度可继续复核",
)
PREFLIGHT_DATE_KEYS = ("trade_date", "source_date", "query_date", "date", "day")
_FILTERED_BY_TRADE_DATE = object()


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


_SOURCE_PAYLOAD_SURFACE_REPLACEMENTS = (
    ("跨线明天先盯哪只", "跨线过程候选回看样本"),
    ("明天先盯哪只", "过程候选回看样本"),
)


def _normalize_source_payload_surface_text(value):
    if isinstance(value, dict):
        return {key: _normalize_source_payload_surface_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_source_payload_surface_text(item) for item in value]
    if isinstance(value, str):
        text = value
        for old, new in _SOURCE_PAYLOAD_SURFACE_REPLACEMENTS:
            text = text.replace(old, new)
        return text
    return value


def _normalize_preflight_date_text(value):
    text = clean_text(value)
    if not text:
        return ""
    text = text.replace("/", "-")
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _preflight_row_source_date(row):
    row = _as_dict(row)
    for key in PREFLIGHT_DATE_KEYS:
        date_text = _normalize_preflight_date_text(row.get(key))
        if date_text:
            return date_text
    return ""


def _preflight_filter_value_to_trade_date(value, expected_trade_date):
    expected_trade_date = _normalize_preflight_date_text(expected_trade_date)
    if not expected_trade_date:
        return value
    if isinstance(value, list):
        filtered = []
        for item in value:
            filtered_item = _preflight_filter_value_to_trade_date(item, expected_trade_date)
            if filtered_item is not _FILTERED_BY_TRADE_DATE:
                filtered.append(filtered_item)
        return filtered
    if isinstance(value, dict):
        source_date = _preflight_row_source_date(value)
        if source_date and source_date != expected_trade_date:
            return _FILTERED_BY_TRADE_DATE
        filtered = {}
        for key, item in value.items():
            filtered_item = _preflight_filter_value_to_trade_date(item, expected_trade_date)
            if filtered_item is _FILTERED_BY_TRADE_DATE:
                continue
            filtered[key] = filtered_item
        return filtered
    return value


def build_sector_capital_preflight_daily_context(*sources, trade_date=""):
    context = {}
    nested_keys = ("observation", "execution_stage_context", "market_research_snapshot")
    for source in sources:
        source = _as_dict(source)
        for key in SECTOR_CAPITAL_PREFLIGHT_DAILY_CONTEXT_KEYS:
            value = _preflight_filter_value_to_trade_date(source.get(key), trade_date)
            if value not in (None, [], {}):
                context[key] = value
        for nested_key in nested_keys:
            nested = _as_dict(source.get(nested_key))
            if nested:
                for key in SECTOR_CAPITAL_PREFLIGHT_DAILY_CONTEXT_KEYS:
                    value = _preflight_filter_value_to_trade_date(nested.get(key), trade_date)
                    if value not in (None, [], {}) and key not in context:
                        context[key] = value
    return context


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
    brooks_price_action_judge = _as_dict(_as_dict(candidate).get("brooks_price_action_judge"))
    if brooks_price_action_judge:
        payload["brooks_price_action_judge"] = dict(brooks_price_action_judge)
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
    if clean_text(layer.get("id")) == "final_action":
        layer["survivors"] = [
            entry
            for entry in entries
            if entry.get("status") in {"final_action", "survived"} and stock_payload(entry.get("stock"))
        ]
    else:
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
            item="周期窗口是否打开",
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
        item = clean_text(row.get("item") or row.get("decision_item") or row.get("决策项"))
        item = item.replace("周期概率窗口", "周期窗口").replace("概率窗口", "周期窗口")
        normalized.append(
            _preflight_decision_row(
                item=item,
                conclusion=row.get("conclusion") or row.get("current_conclusion") or row.get("当前结论"),
                evidence=row.get("evidence") or row.get("facts") or row.get("事实依据"),
                counter_evidence=(
                    clean_text(row.get("counter_evidence") or row.get("反方证据"))
                    .replace("周期概率窗口", "周期窗口")
                    .replace("概率窗口", "周期窗口")
                    .replace("精确胜率", "精确预测")
                ),
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


def _carrier_strategy_primary_stock(strategy):
    strategy = _as_dict(strategy)
    primary = _as_dict(strategy.get("primary_candidate"))
    stock = stock_payload(primary.get("stock"))
    if stock:
        return stock
    label = clean_text(primary.get("stock_label"))
    match = re.match(r"^(?P<name>.+?)\((?P<code>\d{6})\)$", label)
    if match:
        return {"name": clean_text(match.group("name")), "code": clean_text(match.group("code"))}
    return {}


def _carrier_strategy_effective_final_action(final_action, strategy):
    return dict(_as_dict(final_action))


def _preflight_layer_eliminates_stock(layer, stock):
    target_key = stock_key(stock)
    target_label = stock_label(stock)
    if not target_key and not target_label:
        return False
    for entry in _as_list(_as_dict(layer).get("eliminated")) + _as_list(_as_dict(layer).get("entries")):
        entry = _as_dict(entry)
        if clean_text(entry.get("status")) not in {"eliminated", "risk_rejected", "rejected"}:
            continue
        entry_stock = stock_payload(entry.get("stock"))
        entry_key = stock_key(entry_stock) or stock_key(entry)
        entry_label = clean_text(entry.get("stock_label")) or stock_label(entry_stock)
        if target_key and entry_key == target_key:
            return True
        if target_label and entry_label == target_label:
            return True
    return False


def _preflight_layers_eliminate_final_target(layers, final_action):
    target = stock_payload(_as_dict(final_action).get("target"))
    if not target:
        return False
    for layer in _as_list(layers):
        layer_id = clean_text(_as_dict(layer).get("id"))
        if layer_id in {"final_action", "final_resolution"}:
            continue
        if _preflight_layer_eliminates_stock(layer, target):
            return True
    return False


def _sync_preflight_final_action_layer(layers, final_action):
    final_action = _as_dict(final_action)
    target = stock_payload(final_action.get("target"))
    if not target:
        return _normalize_zero_final_action_layer_counts(layers, final_action)
    previous_survivors = []
    for layer in reversed(_as_list(layers)):
        layer = _as_dict(layer)
        if clean_text(layer.get("id")) == "final_action":
            continue
        previous_survivors = [
            entry
            for entry in (_as_list(layer.get("survivors")) or _as_list(layer.get("entries")))
            if _as_dict(entry).get("status") == "survived"
        ]
        if previous_survivors:
            break
    target_key = stock_key(target)
    if not target_key or not any(stock_key(_as_dict(entry).get("stock") or entry) == target_key for entry in previous_survivors):
        return _normalize_zero_final_action_layer_counts(
            layers,
            {
                "label": "0%不参与",
                "position_pct": 0,
                "target": {},
            },
        )
    synced = []
    replaced = False
    final_entry = {
        "stock": target,
        "stock_label": stock_label(target),
        "status": "final_action",
        "reason": clean_text(final_action.get("reason"), "板块资金扩散链路恢复出唯一主样本"),
        "action_label": clean_text(final_action.get("label"), "50%条件执行"),
        "position_pct": _safe_int(final_action.get("position_pct"), default=50),
        "source": clean_text(final_action.get("source"), "sector_capital_carrier_strategy"),
    }
    for layer in _as_list(layers):
        layer = dict(_as_dict(layer))
        if clean_text(layer.get("id")) != "final_action":
            synced.append(layer)
            continue
        layer["input_count"] = max(_safe_int(layer.get("input_count"), default=1), 1)
        layer["eliminated_count"] = 0
        layer["survivor_count"] = 1
        layer["entries"] = [final_entry]
        layer["survivors"] = [final_entry]
        layer["eliminated"] = []
        layer["input_entries"] = [final_entry]
        layer["note"] = "唯一明日动作来自板块资金扩散链路；T+1固定窗口条件不成立则回到0%不参与。"
        synced.append(_normalize_preflight_layer(layer))
        replaced = True
    if not replaced:
        synced.append(
            _normalize_preflight_layer(
                {
                    "id": "final_action",
                    "title": "唯一明日动作",
                    "input_count": 1,
                    "eliminated_count": 0,
                    "survivor_count": 1,
                    "entries": [final_entry],
                    "survivors": [final_entry],
                    "eliminated": [],
                    "input_entries": [final_entry],
                    "note": "唯一明日动作来自板块资金扩散链路；T+1固定窗口条件不成立则回到0%不参与。",
                }
            )
        )
    return synced


def _preflight_layer_by_id(layers, layer_id):
    for layer in _as_list(layers):
        if isinstance(layer, dict) and clean_text(layer.get("id")) == layer_id:
            return layer
    return {}


def _preflight_status_labels(layer, status):
    labels = [
        clean_text(entry.get("stock_label"))
        for entry in _as_list(_as_dict(layer).get("entries"))
        if isinstance(entry, dict) and clean_text(entry.get("status")) == status and clean_text(entry.get("stock_label"))
    ]
    return "、".join(labels) if labels else "无"


def _text_values_from_mapping(value):
    values = []
    if isinstance(value, dict):
        for item in value.values():
            if isinstance(item, (str, int, float)):
                text = clean_text(item)
                if text:
                    values.append(text)
            elif isinstance(item, dict):
                values.extend(_text_values_from_mapping(item))
    elif isinstance(value, (str, int, float)):
        text = clean_text(value)
        if text:
            values.append(text)
    return values


def _t0_market_emotion_state(source_payloads):
    context = _as_dict(_as_dict(source_payloads).get("daily_context"))
    texts = []
    for key in ("market_phase_context", "market_analysis", "market_emotion", "market_overview"):
        texts.extend(_text_values_from_mapping(context.get(key)))
    summary = _as_dict(context.get("mainline_turnover_summary"))
    texts.extend(_text_values_from_mapping(summary))
    joined = "；".join(item for item in texts if item)
    if "冰点" in joined or "退潮" in joined or "偏弱" in joined or "弱修复" in joined:
        return {
            "label": "冰点",
            "cycle": "周期窗口未打开或修复待确认",
            "tplus1": "冰点修复观察",
            "tplus2": "弱修复或震荡",
            "tplus2_cycle": "先按修复失败风险处理",
            "basis": joined,
        }
    if "高潮" in joined or "偏热" in joined or "强攻" in joined:
        return {
            "label": "高潮",
            "cycle": "周期进入兑现复核",
            "tplus1": "高潮惯性",
            "tplus2": "分歧或震荡",
            "tplus2_cycle": "兑现后看承接能否再延续",
            "basis": joined,
        }
    if "震荡" in joined or "分歧" in joined or "修复" in joined:
        return {
            "label": "震荡",
            "cycle": "周期窗口待确认",
            "tplus1": "震荡修复观察",
            "tplus2": "震荡或分歧",
            "tplus2_cycle": "等待价格和板块二次确认",
            "basis": joined,
        }
    hot_plates = _as_list(context.get("hot_plates"))
    fund_inflow = _as_list(_as_dict(context.get("sector_fund_flow")).get("inflow"))
    if len(hot_plates) >= 3 or len(fund_inflow) >= 3:
        return {
            "label": "震荡",
            "cycle": "有局部热度，但整体周期待确认",
            "tplus1": "震荡修复观察",
            "tplus2": "震荡或分歧",
            "tplus2_cycle": "不把局部热度直接升级成新周期",
            "basis": "有热板/资金表事实，但缺少整体市场情绪文本",
        }
    return {
        "label": "",
        "cycle": "",
        "tplus1": "",
        "tplus2": "",
        "tplus2_cycle": "",
        "basis": "",
    }


def _t0_primary_sector(final_action, source_payloads):
    target = stock_payload(_as_dict(final_action).get("target"))
    if target.get("sector"):
        return target.get("sector")
    strategy = _as_dict(_as_dict(source_payloads).get("sector_capital_carrier_strategy"))
    primary = _as_dict(strategy.get("primary_candidate"))
    stock = stock_payload(primary.get("stock"))
    return (
        clean_text(primary.get("sector"))
        or clean_text(stock.get("sector"))
        or clean_text(_as_dict(source_payloads).get("primary_sector"))
    )


def _t0_sector_emotion_state(source_payloads, sector):
    context = _as_dict(_as_dict(source_payloads).get("daily_context"))
    aliases = _sector_aliases(sector)
    if not aliases:
        return {
            "label": "",
            "cycle": "",
            "tplus1": "",
            "tplus2": "",
            "tplus2_cycle": "",
            "basis": "",
        }
    hot_plates = [
        row
        for row in _as_list(context.get("hot_plates"))
        if _sector_aliases(_as_dict(row).get("name")) & aliases
    ]
    fund_rows = []
    for row in _as_list(_as_dict(context.get("sector_fund_flow")).get("inflow")):
        row = _as_dict(row)
        if _sector_aliases(row.get("name")) & aliases:
            fund_rows.append(row)
    limit_rows = []
    for alias in aliases:
        limit_rows.extend(_as_list(_as_dict(context.get("zt_pool_by_sector")).get(alias)))
    if not limit_rows:
        for row in _as_list(context.get("zt_pool")) + _as_list(context.get("lianban_data")):
            if _row_sector_names(row) & aliases:
                limit_rows.append(row)
    evidence = []
    if hot_plates:
        evidence.append("热板出现")
    if fund_rows:
        evidence.append("资金表同向")
    if limit_rows:
        evidence.append(f"同板块涨停{len(limit_rows)}只")
    if hot_plates and fund_rows and limit_rows:
        return {
            "label": "扩散",
            "cycle": "主升或二波确认",
            "tplus1": "板块延续确认",
            "tplus2": "延续后分歧",
            "tplus2_cycle": "强者横住续命，后排先兑现",
            "basis": "、".join(evidence),
        }
    if hot_plates and (fund_rows or limit_rows):
        return {
            "label": "延续",
            "cycle": "二波或趋势延续待确认",
            "tplus1": "板块延续观察",
            "tplus2": "分歧后看承接",
            "tplus2_cycle": "若强者横住才允许继续跟踪",
            "basis": "、".join(evidence),
        }
    if fund_rows or limit_rows:
        return {
            "label": "分歧",
            "cycle": "扩散待确认",
            "tplus1": "分歧承接观察",
            "tplus2": "承接失败则退回观察",
            "tplus2_cycle": "板块不能横住则不继续升级",
            "basis": "、".join(evidence),
        }
    return {
        "label": "",
        "cycle": "",
        "tplus1": "",
        "tplus2": "",
        "tplus2_cycle": "",
        "basis": "",
    }


def _build_tplus_rehearsal(layers, final_action, source_payloads=None):
    layers = _as_list(layers)
    final_action = _as_dict(final_action)
    source_payloads = _as_dict(source_payloads)
    final_position = _safe_int(final_action.get("position_pct"), default=0)
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_target = stock_label(final_action.get("target")) if final_action.get("target") else "无执行对象"
    primary_sector = _t0_primary_sector(final_action, source_payloads)
    market_state = _t0_market_emotion_state(source_payloads)
    sector_state = _t0_sector_emotion_state(source_payloads, primary_sector)
    sector_layer = _preflight_layer_by_id(layers, "sector_capital_diffusion")
    price_layer = _preflight_layer_by_id(layers, "price_action")
    account_layer = _preflight_layer_by_id(layers, "counter_evidence_account") or _preflight_layer_by_id(layers, "account_execution")
    sector_survivors = _preflight_status_labels(sector_layer, "survived")
    price_survivors = _preflight_status_labels(price_layer, "survived")
    has_sector_path = sector_survivors != "无"
    has_price_acceptance = price_survivors != "无"
    final_reason = clean_text(final_action.get("reason")) or _first_entry_reason(account_layer, "eliminated")

    if final_position > 0:
        participation_qualification = "有条件参与"
        market_emotion = market_state.get("tplus1") or "主线延续观察"
        market_cycle = market_state.get("cycle") or "周期窗口打开"
        sector_emotion = sector_state.get("tplus1") or "板块延续"
        sector_cycle = sector_state.get("cycle") or "主升或二波确认"
        tplus2_market_emotion = market_state.get("tplus2") or "延续后分歧或震荡"
        tplus2_market_cycle = market_state.get("tplus2_cycle") or "周期仍在，但进入兑现复核"
        tplus2_sector_emotion = sector_state.get("tplus2") or "延续后分歧"
        tplus2_sector_cycle = sector_state.get("tplus2_cycle") or "强者横住续命，后排先兑现"
        action_bias = f"围绕{final_target}执行，不追无回踩的加速"
    elif has_price_acceptance:
        participation_qualification = "重点观察，不追高"
        market_emotion = market_state.get("tplus1") or "分歧修复观察"
        market_cycle = market_state.get("cycle") or "周期窗口待确认"
        sector_emotion = sector_state.get("tplus1") or "方向有热度但执行资格不足"
        sector_cycle = sector_state.get("cycle") or "扩散待确认"
        tplus2_market_emotion = market_state.get("tplus2") or "震荡或分歧"
        tplus2_market_cycle = market_state.get("tplus2_cycle") or "等待价格和板块二次确认"
        tplus2_sector_emotion = sector_state.get("tplus2") or "分歧后看承接"
        tplus2_sector_cycle = sector_state.get("tplus2_cycle") or "若强者横住才允许继续跟踪"
        action_bias = "只观察承接，不新增参与"
    elif has_sector_path:
        participation_qualification = "只观察承接，不新增参与"
        market_emotion = market_state.get("tplus1") or "分歧轮动"
        market_cycle = market_state.get("cycle") or "周期窗口未打开或待确认"
        sector_emotion = sector_state.get("tplus1") or "板块扩散不足"
        sector_cycle = sector_state.get("cycle") or "一日脉冲待验证"
        tplus2_market_emotion = market_state.get("tplus2") or "震荡偏弱或继续轮动"
        tplus2_market_cycle = market_state.get("tplus2_cycle") or "没有形成可做周期"
        tplus2_sector_emotion = sector_state.get("tplus2") or "退回观察"
        tplus2_sector_cycle = sector_state.get("tplus2_cycle") or "板块不能横住则不继续升级"
        action_bias = "保持空仓或只做旧仓处理"
    else:
        participation_qualification = "不参与"
        market_emotion = market_state.get("tplus1") or "混沌或退潮警戒"
        market_cycle = market_state.get("cycle") or "周期窗口未打开"
        sector_emotion = sector_state.get("tplus1") or "没有确认的主攻方向"
        sector_cycle = sector_state.get("cycle") or "不形成可做板块周期"
        tplus2_market_emotion = market_state.get("tplus2") or "退潮警戒或弱震荡"
        tplus2_market_cycle = market_state.get("tplus2_cycle") or "等待新周期重新出现"
        tplus2_sector_emotion = sector_state.get("tplus2") or "无主线"
        tplus2_sector_cycle = sector_state.get("tplus2_cycle") or "不做板块推升假设"
        action_bias = "不参与，等下一条板块资金路径"

    if final_position > 0:
        buy_windows = [
            "09:30-09:35只观察竞价和开盘承接，不追秒板或一字",
            "09:50-10:10优先等回踩MA5/VWAP/0轴后重新站回",
            "14:30-14:55只在全天承接强且不远离认错线时处理",
        ]
    else:
        buy_windows = [
            "无新增参与窗口；只记录是否出现可复盘的承接",
            "若T+1快速接近涨停或T字强板，标记可能买不到，不补追",
        ]

    return {
        "schema_version": TPLUS_REHEARSAL_SCHEMA_VERSION,
        "t0_boundary": "日报生成日是T0；只使用T0已知事实推演T+1和T+2",
        "review_boundary": "T+1/T+2后验事实只用于复盘批改，不回写T0候选生成或最终动作",
        "basis": "；".join(
            part
            for part in (
                f"最终动作={final_label}",
                f"最终对象={final_target}",
                f"主板块={primary_sector}" if primary_sector else "",
                f"T0市场={market_state.get('label')}" if market_state.get("label") else "",
                f"T0板块={sector_state.get('label')}" if sector_state.get("label") else "",
                f"板块剩余={sector_survivors}",
                f"价格剩余={price_survivors}",
            )
            if part
        ),
        "tplus1": {
            "stage": "T+1参与日预案",
            "participation_qualification": participation_qualification,
            "market_emotion": market_emotion,
            "market_cycle": market_cycle,
            "sector_emotion": sector_emotion,
            "sector_cycle": sector_cycle,
            "buy_windows": buy_windows,
            "confirmation_conditions": [
                "同一板块仍是资金主线或最强扩散方向",
                "资金载体没有被更强同板块锚替代",
                "价格在允许窗口内接受回踩或分歧承接",
                "买点靠近认错线，而不是追高证明自己",
            ],
            "cancellation_conditions": [
                "板块早盘失去扩散或核心掉队",
                "目标直接一字、秒板、T字强板且没有回踩承接",
                "跌破T0关键承接位置后不能收回",
                "同板块出现更强反证，原载体被市场放弃",
            ],
            "missed_entry_plan": "方向对但买点不可达时，记为方向命中但不可买，不把T+2纸面收益算作真实可执行收益",
            "action": action_bias,
            "reason": final_reason or market_state.get("basis") or sector_state.get("basis") or "按T0淘汰赛最终动作推演，不使用T+1事实",
        },
        "tplus2": {
            "stage": "T+2处理日预案",
            "market_emotion": tplus2_market_emotion,
            "market_cycle": tplus2_market_cycle,
            "sector_emotion": tplus2_sector_emotion,
            "sector_cycle": tplus2_sector_cycle,
            "sell_windows": [
                "09:30-09:35先识别退潮、高开兑现或超预期延续",
                "09:50-10:10看承接是否把分歧修复为延续",
                "14:30-14:55按市场周期和板块周期决定兑现、持有或继续观察",
            ],
            "review_points": [
                "T+2实际市场情绪是否符合T0预案",
                "T+2实际板块情绪是否从分歧转延续或扩散",
                "若T+1不可买，T+2收益只保留为方向校准样本",
            ],
            "action": "先按预案处理，再由后验复盘批改",
            "reason": market_state.get("basis") or sector_state.get("basis") or "T0只做两日环境推演，不提前使用T+2收益事实",
        },
    }


def _normalize_text_list(value):
    return [
        clean_text(item)
        for item in _as_list(value)
        if clean_text(item)
    ]


def _normalize_tplus_rehearsal(value, *, layers=None, final_action=None, source_payloads=None):
    rehearsal = _as_dict(value)
    if not rehearsal:
        return _build_tplus_rehearsal(layers or [], final_action or {}, source_payloads=source_payloads)
    normalized = dict(rehearsal)
    normalized["schema_version"] = clean_text(
        normalized.get("schema_version"),
        TPLUS_REHEARSAL_SCHEMA_VERSION,
    )
    normalized["t0_boundary"] = clean_text(
        normalized.get("t0_boundary"),
        "日报生成日是T0；只使用T0已知事实推演T+1和T+2",
    )
    normalized["review_boundary"] = clean_text(
        normalized.get("review_boundary"),
        "T+1/T+2后验事实只用于复盘批改，不回写T0候选生成或最终动作",
    )
    normalized["basis"] = clean_text(normalized.get("basis"))
    for key in ("tplus1", "tplus2"):
        section = dict(_as_dict(normalized.get(key)))
        section["stage"] = clean_text(section.get("stage"), "T+1参与日预案" if key == "tplus1" else "T+2处理日预案")
        for text_key in (
            "participation_qualification",
            "market_emotion",
            "market_cycle",
            "sector_emotion",
            "sector_cycle",
            "missed_entry_plan",
            "action",
            "reason",
        ):
            if text_key in section:
                section[text_key] = clean_text(section.get(text_key))
        for list_key in ("buy_windows", "confirmation_conditions", "cancellation_conditions", "sell_windows", "review_points"):
            if list_key in section:
                section[list_key] = _normalize_text_list(section.get(list_key))
        normalized[key] = section
    return normalized


def _tplus_rehearsal_matches_final_action(rehearsal, final_action):
    rehearsal = _as_dict(rehearsal)
    final_action = _as_dict(final_action)
    target = stock_payload(final_action.get("target"))
    position_pct = _safe_int(final_action.get("position_pct"), default=0)
    tplus1 = _as_dict(rehearsal.get("tplus1"))
    qualification = clean_text(tplus1.get("participation_qualification"))
    basis = clean_text(rehearsal.get("basis"))
    if target and position_pct > 0:
        return qualification == "有条件参与" and stock_label(target) in basis
    return qualification != "有条件参与"


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
        ledger_position_source = (
            ledger.get("position_plan_pct")
            if ledger.get("position_plan_pct") is not None
            else participation.get("position_plan_pct")
        )
        has_ledger_position = ledger_position_source is not None
        ledger_pct = _safe_int(ledger_position_source, default=0) if has_ledger_position else None
        same_final = bool(final_key and final_key == stock_key(candidate))
        if same_final and final_pct > 0:
            extra = {}
            if has_ledger_position:
                extra["ledger_position_pct"] = ledger_pct
            entries.append(
                _candidate_layer_entry(
                    candidate,
                    status="survived",
                    reason=f"最终仓位={final_pct}%",
                    next_basis="进入最终收口层",
                    extra=extra,
                )
            )
            survivors.append(candidate)
            continue
        reason_parts = []
        if missing:
            reason_parts.append("关键数据不完整：" + "、".join(missing))
        if has_ledger_position and ledger_pct <= 0:
            reason_parts.append("决策台账仓位=0%")
        elif not has_ledger_position:
            reason_parts.append("账户/仓位事实缺失")
        if participation.get("action") == "skip":
            reason_parts.append("计划动作=skip")
        if final_pct <= 0:
            reason_parts.append(final_action.get("label") or "0%不参与")
        extra = {"missing_data": missing}
        if has_ledger_position:
            extra["ledger_position_pct"] = ledger_pct
        entries.append(
            _candidate_layer_entry(
                candidate,
                status="eliminated",
                reason="；".join(clean_text(item) for item in reason_parts if clean_text(item))
                or final_action.get("reason")
                or "账户、仓位或盈亏比证据不足",
                elimination_basis="不取得明日新增参与资格",
                extra=extra,
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


def _input_entries_for_layer(layer):
    layer = _as_dict(layer)
    entries = _as_list(layer.get("input_entries")) if "input_entries" in layer else _as_list(layer.get("entries"))
    return [
        _normalize_preflight_entry(entry)
        for entry in entries
        if isinstance(entry, dict)
    ]


def _same_stock_set(entries, allowed_keys):
    allowed_keys = set(allowed_keys or set())
    if not allowed_keys:
        return []
    return [
        entry
        for entry in _as_list(entries)
        if stock_key(_as_dict(entry).get("stock")) in allowed_keys
    ]


def _empty_following_layer(layer, previous_title):
    layer = dict(_as_dict(layer))
    existing_note = clean_text(layer.get("note"))
    layer["entries"] = []
    layer["input_entries"] = []
    layer["input_count"] = 0
    layer["eliminated_count"] = 0
    layer["survivor_count"] = 0
    layer["eliminated"] = []
    layer["survivors"] = []
    layer["note"] = "；".join(
        part
        for part in (
            f"上一层{clean_text(previous_title, '复核')}没有剩余股票，本层不再新增过程样本。",
            existing_note,
        )
        if part
    )
    return layer


def _enforce_preflight_monotonic_layers(layers):
    normalized = []
    previous_survivor_keys = None
    previous_title = ""
    for raw_layer in _as_list(layers):
        layer = _normalize_preflight_layer(raw_layer)
        layer_id = clean_text(layer.get("id"))
        if layer_id == "final_action":
            if previous_survivor_keys is not None:
                layer["input_entries"] = _same_stock_set(_input_entries_for_layer(layer), previous_survivor_keys)
                layer["input_count"] = len(layer["input_entries"])
            normalized.append(layer)
            previous_title = clean_text(layer.get("title"))
            continue
        if previous_survivor_keys is None:
            normalized.append(layer)
            previous_survivor_keys = {
                stock_key(entry.get("stock"))
                for entry in _entries_with_status(layer.get("entries"), "survived")
                if stock_key(entry.get("stock"))
            }
            previous_title = clean_text(layer.get("title"))
            continue
        if not previous_survivor_keys:
            layer = _empty_following_layer(layer, previous_title)
            normalized.append(layer)
            previous_survivor_keys = set()
            previous_title = clean_text(layer.get("title"))
            continue
        entries = _same_stock_set(_as_list(layer.get("entries")), previous_survivor_keys)
        layer["entries"] = entries
        layer["input_entries"] = _same_stock_set(_input_entries_for_layer(layer), previous_survivor_keys)
        if not layer["input_entries"]:
            layer["input_entries"] = list(entries)
        layer["input_count"] = len(layer["input_entries"])
        layer["eliminated"] = _entries_with_status(entries, "eliminated")
        layer["survivors"] = _entries_with_status(entries, "survived")
        layer["eliminated_count"] = len(layer["eliminated"])
        layer["survivor_count"] = len(layer["survivors"])
        normalized.append(layer)
        previous_survivor_keys = {
            stock_key(entry.get("stock"))
            for entry in layer["survivors"]
            if stock_key(entry.get("stock"))
        }
        previous_title = clean_text(layer.get("title"))
    return normalized


def _is_legacy_signal_entry(entry):
    entry = _as_dict(entry)
    reason_text = clean_text(
        entry.get("reason")
        or entry.get("elimination_basis")
        or entry.get("entry_basis")
        or entry.get("entered_reason")
    )
    return (
        clean_text(entry.get("candidate_origin")) == "legacy_signal_only"
        or LEGACY_SIGNAL_ONLY_REASON in reason_text
    )


def _stock_code_from_row(row):
    row = _as_dict(row)
    return normalize_stock_code(
        row.get("code")
        or row.get("stock_code")
        or row.get("代码")
        or row.get("symbol")
    )


def _sector_aliases(value):
    text = clean_text(value)
    if not text:
        return set()
    aliases = {text}
    if text in {"火力发电", "新型电力", "绿色电力", "风电", "超超临界发电"}:
        aliases.add("电力")
    if text == "电力":
        aliases.update({"火力发电", "新型电力", "绿色电力", "风电", "超超临界发电"})
    return aliases


def _row_sector_names(row):
    row = _as_dict(row)
    sectors = set()
    for key in ("sector", "sector_name", "sector_candidate", "industry", "所属行业", "name"):
        sectors.update(_sector_aliases(row.get(key)))
    for key in ("concepts", "tags", "xuangubao_related_plate_names"):
        for item in _as_list(row.get(key)):
            sectors.update(_sector_aliases(item))
    for item in _as_list(row.get("xuangubao_related_plates")):
        sectors.update(_sector_aliases(_as_dict(item).get("plate_name")))
    return {item for item in sectors if item}


def _preflight_fact_indexes(source_payloads):
    source_payloads = _as_dict(source_payloads)
    context = _as_dict(source_payloads.get("daily_context"))

    hot_by_code = {}
    for key in ("hot_rank_top50", "hot_rank_top30", "integrated_hot_list"):
        for row in _as_list(context.get(key)):
            code = _stock_code_from_row(row)
            if code and code not in hot_by_code:
                hot_by_code[code] = _as_dict(row)

    limit_by_code = {}
    sector_limit_map = {}
    for row in _as_list(context.get("zt_pool")) + _as_list(context.get("lianban_data")):
        row = _as_dict(row)
        code = _stock_code_from_row(row)
        if code and code not in limit_by_code:
            limit_by_code[code] = row
        for sector in _row_sector_names(row):
            sector_limit_map.setdefault(sector, []).append(row)
    for sector, rows in _as_dict(context.get("zt_pool_by_sector")).items():
        for row in _as_list(rows):
            row = _as_dict(row)
            for alias in _sector_aliases(sector):
                sector_limit_map.setdefault(alias, []).append(row)
            code = _stock_code_from_row(row)
            if code and code not in limit_by_code:
                limit_by_code[code] = row

    hot_plate_names = []
    hot_plate_rows = []
    for row in _as_list(context.get("hot_plates")):
        row = _as_dict(row)
        name = clean_text(row.get("name"))
        if name:
            hot_plate_names.append(name)
            hot_plate_rows.append(row)

    fund_flow_names = []
    for key in ("inflow", "outflow"):
        for row in _as_list(_as_dict(context.get("sector_fund_flow")).get(key)):
            name = clean_text(_as_dict(row).get("name"))
            if name:
                fund_flow_names.append(name)

    attack_rows_by_sector = {}
    for row in _as_list(context.get("sector_attack_evidence_rows")):
        row = _as_dict(row)
        sector = clean_text(row.get("sector_name"))
        if sector:
            attack_rows_by_sector.setdefault(sector, []).append(row)

    current_mainline = _as_dict(context.get("current_mainline_history_record"))
    current_snapshot = _as_dict(context.get("current_sector_turnover_snapshot"))
    crossline_rows = []
    for row in _as_list(context.get("crossline_observation_stocks")):
        if isinstance(row, dict):
            crossline_rows.append(row)
    watch_anchor = _as_dict(context.get("watch_anchor"))
    if watch_anchor:
        crossline_rows.append(watch_anchor)
    special_probe = _as_dict(context.get("special_probe_verdict"))
    probe_candidate = _as_dict(special_probe.get("probe_candidate"))
    if probe_candidate:
        crossline_rows.append(probe_candidate)
    crossline_by_code = {}
    for row in crossline_rows:
        code = _stock_code_from_row(row)
        if code:
            crossline_by_code.setdefault(code, []).append(row)

    tracking_by_code = {}
    tracking = _as_dict(context.get("tracking_memory_status"))
    for key in ("validated_items", "total_items", "tentative_items", "inactive_items"):
        for row in _as_list(tracking.get(key)):
            row = _as_dict(row)
            code = _stock_code_from_row(row)
            if code:
                tracking_by_code.setdefault(code, []).append(row)

    recent_extreme_by_code = {}
    recent_extreme_by_sector = {}
    for key in ("recent_extreme_conviction_mentions", "recent_extreme_conviction_mentions_for_review"):
        for row in _as_list(context.get(key)):
            row = _as_dict(row)
            code = _stock_code_from_row(row)
            if code:
                recent_extreme_by_code.setdefault(code, []).append(row)
            for sector in _row_sector_names(row):
                recent_extreme_by_sector.setdefault(sector, []).append(row)

    return {
        "hot_by_code": hot_by_code,
        "limit_by_code": limit_by_code,
        "sector_limit_map": sector_limit_map,
        "hot_plate_rows": hot_plate_rows,
        "hot_plate_names": hot_plate_names,
        "fund_flow_names": fund_flow_names,
        "attack_rows_by_sector": attack_rows_by_sector,
        "current_mainline": current_mainline,
        "current_snapshot": current_snapshot,
        "crossline_by_code": crossline_by_code,
        "tracking_by_code": tracking_by_code,
        "recent_extreme_by_code": recent_extreme_by_code,
        "recent_extreme_by_sector": recent_extreme_by_sector,
    }


def _sector_has_name(names, sector):
    aliases = _sector_aliases(sector)
    return any(_sector_aliases(name) & aliases for name in names)


def _entry_context_rows(entry, fact_indexes):
    entry = _as_dict(entry)
    fact_indexes = _as_dict(fact_indexes)
    code = clean_text(entry.get("stock_code"))
    rows = []
    for key in ("crossline_by_code", "tracking_by_code", "recent_extreme_by_code"):
        rows.extend(_as_list(_as_dict(fact_indexes.get(key)).get(code)))
    return [_as_dict(row) for row in rows if isinstance(row, dict)]


def _entry_trend_second_wave_text(entry, fact_indexes=None):
    entry = _as_dict(entry)
    brooks = _as_dict(entry.get("brooks_price_action_judge"))
    pieces = [
        entry.get("sector_role"),
        entry.get("reason"),
        entry.get("entry_basis"),
        entry.get("entered_reason"),
        entry.get("current_reason"),
        entry.get("eliminated_reason"),
        brooks.get("status"),
        brooks.get("verdict"),
        brooks.get("participation_effect"),
    ]
    for row in _entry_context_rows(entry, fact_indexes):
        pieces.extend(
            [
                row.get("source_tier"),
                row.get("source"),
                row.get("pattern"),
                row.get("reason"),
                row.get("tomorrow_expectation"),
                row.get("follow_state"),
                row.get("status"),
            ]
        )
    return "；".join(clean_text(piece) for piece in pieces if clean_text(piece))


def _has_trend_second_wave_evidence(entry, fact_indexes=None):
    entry = _as_dict(entry)
    brooks_status = clean_text(_as_dict(entry.get("brooks_price_action_judge")).get("status"))
    if brooks_status in {"risk_first", "price_rejected"}:
        return False
    return _contains_any(_entry_trend_second_wave_text(entry, fact_indexes), TREND_SECOND_WAVE_MARKERS)


def _sector_context_supports_entry(entry, fact_indexes):
    entry = _as_dict(entry)
    fact_indexes = _as_dict(fact_indexes)
    sector = clean_text(entry.get("sector") or _as_dict(entry.get("stock")).get("sector"))
    if not sector:
        return False
    current_mainline = _as_dict(fact_indexes.get("current_mainline"))
    mainline_names = [
        current_mainline.get("leading_line"),
        current_mainline.get("primary_mainline"),
        current_mainline.get("mainline"),
    ]
    current_snapshot = _as_dict(fact_indexes.get("current_snapshot"))
    snapshot_names = [
        current_snapshot.get("sector_name"),
        current_snapshot.get("name"),
    ]
    selected_hot_plate_names = []
    for row in _as_list(fact_indexes.get("hot_plate_rows")):
        row = _as_dict(row)
        order = _safe_int(row.get("order") or row.get("rank"), default=99)
        if order <= 3:
            selected_hot_plate_names.append(row.get("name"))
    return any(
        (
            _sector_has_name(mainline_names, sector),
            _sector_has_name(snapshot_names, sector),
            _sector_has_name(selected_hot_plate_names, sector),
        )
    )


def _legacy_trend_second_wave_reason(entry, fact_indexes):
    base_reason = _leader_reverse_reason(entry, fact_indexes)
    suffix = "趋势龙头/二波预期只取得继续反推资格，仍需与板块锚和同板块容量核心对照，不直接生成明日对象"
    if suffix in base_reason:
        return base_reason
    return f"{base_reason}；{suffix}"


def _trend_context_reason_bits(entry, fact_indexes):
    bits = []
    for row in _entry_context_rows(entry, fact_indexes):
        source = clean_text(row.get("source") or row.get("source_tier"))
        pattern = clean_text(row.get("pattern"))
        follow_state = clean_text(row.get("follow_state"))
        reason = clean_text(row.get("reason") or row.get("tomorrow_expectation"))
        if source or pattern:
            bits.append("趋势/二波线索=" + "/".join(part for part in (source, pattern) if part))
        if follow_state:
            bits.append(f"跟踪记忆={follow_state}")
        if reason and reason not in bits:
            bits.append(f"观察理由={reason}")
    sector = clean_text(_as_dict(entry).get("sector") or _as_dict(_as_dict(entry).get("stock")).get("sector"))
    anchor_labels = []
    seen = set()
    for alias in _sector_aliases(sector):
        for row in _as_list(_as_dict(fact_indexes).get("recent_extreme_by_sector", {}).get(alias)):
            label = stock_label(
                {
                    "name": row.get("stock_name") or row.get("name"),
                    "code": row.get("stock_code") or row.get("code"),
                    "sector": row.get("sector_candidate") or row.get("sector"),
                }
            )
            reason = clean_text(row.get("reason"))
            if label and label != "暂无" and label not in seen:
                seen.add(label)
                anchor_labels.append(label + (f"({reason})" if reason else ""))
    if anchor_labels:
        bits.append("同板块趋势锚=" + "、".join(anchor_labels[:2]))
    return bits


def _leader_reverse_reason(entry, fact_indexes):
    entry = _as_dict(entry)
    code = clean_text(entry.get("stock_code"))
    sector = clean_text(entry.get("sector"))
    hot_row = _as_dict(_as_dict(fact_indexes).get("hot_by_code", {}).get(code))
    limit_row = _as_dict(_as_dict(fact_indexes).get("limit_by_code", {}).get(code))
    sector_limit_rows = []
    seen_sector_limit_keys = set()
    for alias in _sector_aliases(sector):
        for row in _as_list(_as_dict(fact_indexes).get("sector_limit_map", {}).get(alias)):
            row = _as_dict(row)
            row_key = _stock_code_from_row(row) or clean_text(row.get("stock_label") or row.get("name") or row.get("stock_name"))
            if row_key and row_key in seen_sector_limit_keys:
                continue
            if row_key:
                seen_sector_limit_keys.add(row_key)
            sector_limit_rows.append(row)

    hot_bits = []
    hot_rank = hot_row.get("rank") or hot_row.get("order")
    if hot_rank:
        hot_bits.append(f"热榜第{hot_rank}")
    concepts = [clean_text(item) for item in _as_list(hot_row.get("concepts") or hot_row.get("tags")) if clean_text(item)]
    if concepts:
        hot_bits.append("概念=" + "、".join(concepts[:3]))
    if limit_row:
        boards = limit_row.get("连板数") or limit_row.get("lianban_days") or limit_row.get("xuangubao_limit_up_days")
        limit_bits = ["自身涨停"]
        if boards:
            limit_bits.append(f"连板/高度={boards}")
        hot_bits.append("、".join(limit_bits))

    sector_bits = []
    current_mainline = _as_dict(fact_indexes.get("current_mainline"))
    leading_line = clean_text(current_mainline.get("leading_line") or current_mainline.get("primary_mainline"))
    if leading_line:
        sector_bits.append(f"当日记录主线={leading_line}")
    current_snapshot = _as_dict(fact_indexes.get("current_snapshot"))
    snapshot_name = clean_text(current_snapshot.get("sector_name"))
    snapshot_share = current_snapshot.get("sector_turnover_share_pct") or current_snapshot.get("turnover_share_pct")
    if snapshot_name:
        if snapshot_share not in (None, ""):
            sector_bits.append(f"成交跟踪板块={snapshot_name}({snapshot_share}%)")
        else:
            sector_bits.append(f"成交跟踪板块={snapshot_name}")
    if _sector_has_name(_as_list(fact_indexes.get("hot_plate_names")), sector):
        sector_bits.append("板块在热度板块榜")
    if _sector_has_name(_as_list(fact_indexes.get("fund_flow_names")), sector):
        sector_bits.append("板块出现在资金流向表")
    if sector_limit_rows:
        labels = []
        seen_labels = set()
        for row in sector_limit_rows[:3]:
            label = stock_label(row)
            if not label:
                label = clean_text(row.get("name") or row.get("名称"))
            if label and label not in seen_labels:
                seen_labels.add(label)
                labels.append(label)
        if labels:
            sector_bits.append("同板块涨停=" + "、".join(labels))

    role = clean_text(entry.get("sector_role"))
    reversal = clean_text(entry.get("reversal_decision"))
    role_bits = []
    if role:
        role_bits.append(f"角色={role}")
    if reversal:
        role_bits.append(f"反推={reversal}")

    trend_bits = _trend_context_reason_bits(entry, fact_indexes)
    facts = "；".join(bit for bit in hot_bits + sector_bits + role_bits + trend_bits if bit)
    if not facts:
        facts = "缺少热榜、板块扩散、同板块涨停或角色反推证据"
    role_is_proven = bool(
        reversal in PASS_REVERSAL_DECISIONS
        or (role and _contains_any(role, CORE_ROLE_MARKERS) and not _contains_any(role, PROCESS_ONLY_ROLE_MARKERS))
    )
    if not role_is_proven:
        return (
            f"{facts}；尚未证明它就是该板块锚/龙头，不能把涨停或热榜直接等同于板块龙头，不能作为新仓入口"
        )
    return f"{facts}；仍需与板块锚和同板块容量核心对照"


def _build_market_capital_structure_layer(sector_layer, source_payloads=None):
    fact_indexes = _preflight_fact_indexes(source_payloads)
    entries = []
    for entry in _entries_for_layer(sector_layer):
        if _is_legacy_signal_entry(entry):
            copied = dict(entry)
            if _has_trend_second_wave_evidence(entry, fact_indexes) and _sector_context_supports_entry(entry, fact_indexes):
                copied.update(
                    {
                        "status": "survived",
                        "reason": _legacy_trend_second_wave_reason(entry, fact_indexes),
                        "next_basis": "进入板块资金扩散层",
                        "elimination_basis": "",
                    }
                )
                entries.append(copied)
                continue
            copied.update(
                {
                    "status": "eliminated",
                    "reason": _leader_reverse_reason(entry, fact_indexes),
                    "next_basis": "",
                    "elimination_basis": "需要先证明板块资金扩散，再证明它是板块锚/龙头；涨停或热榜本身只作线索",
                }
            )
            entries.append(copied)
            continue
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
            "note": (
                "先判断资金是否选择了可扩散方向；涨停、热榜和旧记忆只作过程证据。"
                if entries
                else "目标日期没有可复核的板块资金扩散入口。"
            ),
        }
    )


def _build_capital_carrier_from_sector_layer(sector_layer):
    entries = []
    for entry in _entries_for_layer(sector_layer):
        if entry.get("status") != "survived":
            continue
        copied = dict(entry)
        if _has_trend_second_wave_evidence(copied):
            copied.update(
                {
                    "status": "survived",
                    "reason": "板块资金扩散已支持，趋势龙头/二波预期进入资金载体角色反推",
                    "next_basis": "进入资金载体角色反推",
                    "elimination_basis": "",
                }
            )
        else:
            copied.update(
                {
                    "status": "eliminated",
                    "reason": clean_text(copied.get("reason"), "板块扩散有线索，但资金载体身份未证明"),
                    "next_basis": "",
                    "elimination_basis": "未证明是板块内资金反复回看的趋势容量、板块锚或分支核心",
                }
            )
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "capital_carrier",
            "title": "板块内资金载体",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(sector_layer).get("source_layer_id") or _as_dict(sector_layer).get("id")),
            "note": (
                "只接收上一层剩余股票；趋势/二波只表示资金载体候选，不等同于最终对象。"
                if entries
                else "上一层没有剩余股票；资金载体层无输入。"
            ),
        }
    )


def _build_carrier_role_from_carrier_layer(carrier_layer, source_payloads=None):
    fact_indexes = _preflight_fact_indexes(source_payloads)
    entries = []
    for entry in _entries_for_layer(carrier_layer):
        if entry.get("status") != "survived":
            continue
        copied = dict(entry)
        reversal = clean_text(copied.get("reversal_decision"))
        role = clean_text(copied.get("sector_role"))
        role_is_proven = bool(
            reversal in PASS_REVERSAL_DECISIONS
            or (role and _contains_any(role, CORE_ROLE_MARKERS) and not _contains_any(role, PROCESS_ONLY_ROLE_MARKERS))
        )
        if role_is_proven and not _is_legacy_signal_entry(copied):
            copied.update(
                {
                    "status": "survived",
                    "reason": _leader_reverse_reason(copied, fact_indexes),
                    "next_basis": "进入量化参与痕迹层",
                    "elimination_basis": "",
                }
            )
        elif (
            _is_legacy_signal_entry(copied)
            and _has_trend_second_wave_evidence(copied, fact_indexes)
            and _sector_context_supports_entry(copied, fact_indexes)
        ):
            copied.update(
                {
                    "status": "survived",
                    "reason": _legacy_trend_second_wave_reason(copied, fact_indexes),
                    "next_basis": "进入量化参与痕迹层，继续看价格是否接受",
                    "elimination_basis": "",
                }
            )
        else:
            copied.update(
                {
                    "status": "eliminated",
                    "reason": _legacy_trend_second_wave_reason(copied, fact_indexes),
                    "next_basis": "",
                    "elimination_basis": "仍需与板块锚和同板块容量核心对照，不能只凭趋势/二波预期取得新增参与资格",
                }
            )
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "carrier_role",
            "title": "资金载体角色反推",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(carrier_layer).get("source_layer_id") or _as_dict(carrier_layer).get("id")),
            "note": (
                "本层回答它是否已经证明为板块锚/龙头；趋势/二波候选若不能完成反推，仍在这里停止。"
                if entries
                else "上一层没有剩余股票；角色反推层无输入。"
            ),
        }
    )


def _build_quant_trace_layer(role_layer, price_layer):
    role_entries = _entries_for_layer(role_layer)
    price_entries = _entries_for_layer(price_layer)
    price_by_key = {stock_key(entry.get("stock")): entry for entry in price_entries if stock_key(entry.get("stock"))}
    entries = []
    for entry in role_entries:
        if entry.get("status") != "survived":
            continue
        key = stock_key(entry.get("stock"))
        price_entry = price_by_key.get(key, {})
        status = "survived"
        reason = "重心抬高、回踩承接和放量不崩进入价格行为复核"
        next_basis = "进入价格行为确认层"
        elimination_basis = ""
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
            "note": "只记录可见行为：重心抬高、回踩承接、放量不崩、缩量不死；不写成确定是哪类资金买入。",
        }
    )


def _build_price_action_from_quant_layer(quant_layer):
    entries = []
    for entry in _entries_for_layer(quant_layer):
        if entry.get("status") != "survived":
            continue
        copied = dict(entry)
        reason = _price_action_reason(copied, {})
        brooks_status = clean_text(_as_dict(copied.get("brooks_price_action_judge")).get("status"))
        reason_text = "；".join(
            clean_text(part)
            for part in (
                reason,
                copied.get("reason"),
                copied.get("elimination_basis"),
                copied.get("next_basis"),
            )
            if clean_text(part)
        )
        accepted = brooks_status == "accepted" or _contains_any(reason_text, PRICE_ACTION_ACCEPT_MARKERS)
        if (
            brooks_status in {"risk_first", "price_rejected", "needs_second_confirmation", "insufficient"}
            or _contains_any(reason_text, PRICE_ACTION_REJECT_MARKERS)
            or not accepted
        ):
            copied.update(
                {
                    "status": "eliminated",
                    "reason": reason or clean_text(copied.get("reason")) or "价格行为仍需确认",
                    "next_basis": "",
                    "elimination_basis": "趋势载体已识别，但价格接受度不足，不能取得新增参与资格",
                }
            )
        else:
            copied.update(
                {
                    "status": "survived",
                    "reason": reason or "价格行为未见明确破坏，继续进入周期窗口复核",
                    "next_basis": "进入周期窗口",
                    "elimination_basis": "",
                }
            )
        entries.append(copied)
    return _normalize_preflight_layer(
        {
            "id": "price_action",
            "title": "价格行为确认",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(quant_layer).get("source_layer_id") or _as_dict(quant_layer).get("id")),
            "note": (
                "趋势资金载体必须再通过价格行为复核；价格不接受时只保留观察，不新增参与。"
                if entries
                else "上一层没有剩余股票；价格行为层无输入。"
            ),
        }
    )


def _build_cycle_window_layer(price_layer, final_action, account_layer=None):
    final_action = _as_dict(final_action)
    final_position = _safe_int(final_action.get("position_pct"), default=0)
    final_reason = clean_text(final_action.get("reason"))
    failure_conditions = [
        clean_text(item)
        for item in _as_list(final_action.get("failure_conditions"))
        if clean_text(item)
    ]
    account_by_key = {
        stock_key(entry.get("stock")): entry
        for entry in _entries_for_layer(account_layer)
        if stock_key(entry.get("stock"))
    }
    entries = []
    for entry in _entries_for_layer(price_layer):
        if entry.get("status") != "survived":
            continue
        has_account_detail = stock_key(entry.get("stock")) in account_by_key
        if entry.get("status") == "survived" and (final_position > 0 or has_account_detail):
            status = "survived"
            reason = "市场、板块、资金载体和价格行为同向，进入账户/盈亏比复核"
            next_basis = "进入账户/盈亏比/时间窗口"
            elimination_basis = ""
        else:
            status = "eliminated"
            if failure_conditions:
                unmet = "；未满足条件：" + "、".join(failure_conditions)
                reason = f"价格行为通过，但周期窗口未打开或账户/时间条件未满足{unmet}"
                if final_reason:
                    reason = f"{reason}；{final_reason}"
                elimination_basis = (
                    f"最终动作未给出新增参与资格：{final_reason}"
                    if final_reason
                    else "周期窗口、账户边界或时间窗口没有给出新增参与资格"
                )
            else:
                reason = "价格行为通过，但最终动作未给出具体失败条件，待补周期/账户/时间窗口理由"
                if final_reason:
                    reason = f"{reason}；{final_reason}"
                elimination_basis = (
                    f"最终动作未给出新增参与资格但缺少具体失败条件：{final_reason}"
                    if final_reason
                    else "最终动作缺少具体失败条件"
                )
            next_basis = ""
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
            "id": "cycle_window",
            "title": "周期窗口",
            "entries": entries,
            "source_layer_id": clean_text(_as_dict(price_layer).get("source_layer_id") or _as_dict(price_layer).get("id")),
            "note": "周期窗口只作条件链合并判断，不输出精确预测。",
        }
    )


def _build_counter_evidence_account_layer(cycle_layer, account_layer, final_action):
    final_action = _as_dict(final_action)
    account_entries = _entries_for_layer(account_layer)
    account_by_key = {stock_key(entry.get("stock")): entry for entry in account_entries if stock_key(entry.get("stock"))}
    entries = []
    for entry in _entries_for_layer(cycle_layer):
        key = stock_key(entry.get("stock"))
        account_entry = account_by_key.get(key, {})
        if account_entry:
            copied = dict(account_entry)
            entries.append(copied)
        else:
            copied = dict(entry)
            copied["status"] = "eliminated"
            copied["reason"] = clean_text(entry.get("reason")) or clean_text(final_action.get("reason")) or "反方证据未解除"
            copied["elimination_basis"] = clean_text(entry.get("elimination_basis")) or "反方证据或账户边界未满足"
            copied["next_basis"] = ""
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


def _build_sector_capital_preflight_layers(raw_layers, final_action, source_payloads=None):
    copied_layers = [_copy_preflight_layer(layer) for layer in _as_list(raw_layers) if isinstance(layer, dict)]
    for layer in copied_layers:
        layer_id = clean_text(layer.get("id"))
        title = clean_text(layer.get("title"))
        if layer_id in {"cycle_probability_window", "cycle_probability"} or title == "周期概率窗口":
            layer["id"] = "cycle_window"
            layer["title"] = "周期窗口"
            note = clean_text(layer.get("note"))
            if note:
                layer["note"] = (
                    note.replace("周期概率窗口", "周期窗口")
                    .replace("概率窗口", "周期窗口")
                    .replace("精确胜率", "精确预测")
                )
            for entry in _as_list(layer.get("entries")):
                if not isinstance(entry, dict):
                    continue
                for key in ("reason", "next_basis", "elimination_basis"):
                    text = clean_text(entry.get(key))
                    if text:
                        entry[key] = (
                            text.replace("周期概率窗口", "周期窗口")
                            .replace("概率窗口", "周期窗口")
                            .replace("精确胜率", "精确预测")
                        )
    by_id = {clean_text(layer.get("id")): layer for layer in copied_layers}
    if {
        "market_capital_structure",
        "sector_capital_diffusion",
    }.issubset(by_id):
        ordered = []
        for layer_id in SECTOR_CAPITAL_PREFLIGHT_LAYER_ORDER:
            layer = by_id.get(layer_id)
            if layer:
                ordered.append(_normalize_preflight_layer(layer))
        for layer in copied_layers:
            layer_id = clean_text(layer.get("id"))
            if (
                layer_id
                and layer_id not in SECTOR_CAPITAL_PREFLIGHT_LAYER_ORDER
                and layer_id != "legacy_signal_recycle"
            ):
                ordered.append(_normalize_preflight_layer(layer))
        return _enforce_preflight_monotonic_layers(ordered)

    sector_layer = by_id.get("sector_capital_diffusion") or {}
    carrier_layer = by_id.get("capital_carrier") or {}
    role_layer = by_id.get("carrier_role") or carrier_layer
    price_layer = by_id.get("price_action") or {}
    account_layer = by_id.get("account_execution") or {}
    final_layer = by_id.get("final_action") or {}

    market_layer = _build_market_capital_structure_layer(sector_layer, source_payloads=source_payloads)
    sector_layer = _normalize_preflight_layer(
        {
            "id": "sector_capital_diffusion",
            "title": "板块资金扩散",
            "entries": _entries_with_status(_as_list(market_layer.get("entries")), "survived"),
            "source_layer_id": clean_text(_as_dict(sector_layer).get("source_layer_id") or _as_dict(sector_layer).get("id")),
            "note": (
                "只接收上一层已经证明来自市场资金结构选择的股票。"
                if _entries_with_status(_as_list(market_layer.get("entries")), "survived")
                else "上一层没有剩余股票；目标日期没有股票能从旧涨停/连板/热榜样本升级为板块资金扩散入口。"
            ),
        }
    )
    if not _entries_for_layer(carrier_layer):
        carrier_layer = _build_capital_carrier_from_sector_layer(sector_layer)
    else:
        carrier_layer = _normalize_preflight_layer(carrier_layer)
    if not _entries_for_layer(role_layer):
        role_layer = _build_carrier_role_from_carrier_layer(carrier_layer, source_payloads=source_payloads)
    else:
        role_layer = _normalize_preflight_layer(role_layer)
    if not _as_dict(price_layer).get("id"):
        price_layer = _normalize_preflight_layer(
            {
                "id": "price_action",
                "title": "价格行为确认",
                "entries": [],
                "note": "上一层没有剩余股票；价格行为层无输入。",
            }
        )
    else:
        price_layer = _normalize_preflight_layer(price_layer)
    if not _as_dict(final_layer).get("id"):
        final_target = stock_payload(_as_dict(final_action).get("target"))
        final_entry = {
            "stock": final_target,
            "stock_label": stock_label(final_target) if final_target else "无执行对象",
            "status": "final_action",
            "reason": clean_text(_as_dict(final_action).get("reason"), "最终没有新增参与对象"),
            "action_label": clean_text(_as_dict(final_action).get("label"), "0%不参与"),
            "position_pct": _safe_int(_as_dict(final_action).get("position_pct"), default=0),
        }
        final_layer = _normalize_preflight_layer(
            {
                "id": "final_action",
                "title": "唯一明日动作",
                "entries": [final_entry],
                "note": "最终动作只来自已解析结论；本页不新增第二个明日对象。",
            }
        )
        if not final_target:
            final_layer["input_count"] = 0
    else:
        final_layer = _normalize_preflight_layer(final_layer)
    quant_layer = _build_quant_trace_layer(role_layer, price_layer)
    if not _entries_for_layer(price_layer):
        price_layer = _build_price_action_from_quant_layer(quant_layer)
    cycle_layer = _build_cycle_window_layer(price_layer, final_action, account_layer)
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


def _normalize_zero_final_action_layer_counts(layers, final_action):
    if stock_payload(_as_dict(final_action).get("target")):
        return _as_list(layers)
    normalized = []
    for layer in _as_list(layers):
        layer = dict(_as_dict(layer))
        if clean_text(layer.get("id")) == "final_action":
            layer["input_count"] = 0
            layer["eliminated_count"] = 0
            layer["survivor_count"] = 0
            layer["survivors"] = []
            layer["eliminated"] = []
            layer["input_entries"] = []
        normalized.append(layer)
    return normalized


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
                "sector_capital_carrier_strategy",
                "daily_context",
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
        "sector_capital_carrier_strategy": dict(_as_dict(source_bundle.get("sector_capital_carrier_strategy"))),
        "daily_context": dict(_as_dict(source_bundle.get("daily_context"))),
    }
    if not any(normalized.values()) and isinstance(elimination_tournament_payload, dict) and elimination_tournament_payload:
        normalized["elimination_tournament_payload"] = dict(elimination_tournament_payload)
    return _normalize_source_payload_surface_text(normalized)


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
    normalized["sector_capital_carrier_strategy"] = _as_dict(
        normalized.get("sector_capital_carrier_strategy")
        or normalized["source_payloads"].get("sector_capital_carrier_strategy")
    )
    if normalized["sector_capital_carrier_strategy"]:
        normalized["source_payloads"]["sector_capital_carrier_strategy"] = dict(
            normalized["sector_capital_carrier_strategy"]
        )
    final_action = _as_dict(normalized.get("final_action"))
    normalized["final_action"] = {
        "label": clean_text(final_action.get("label"), "0%不参与"),
        "position_pct": _safe_int(final_action.get("position_pct"), default=0),
        "target": stock_payload(final_action.get("target")),
        "source": clean_text(final_action.get("source"), "final_target_resolution"),
        "reason": clean_text(final_action.get("reason")),
        "failure_conditions": [
            clean_text(item)
            for item in _as_list(final_action.get("failure_conditions"))
            if clean_text(item)
        ],
    }
    if normalized["final_action"]["position_pct"] <= 0:
        normalized["final_action"]["position_pct"] = 0
        normalized["final_action"]["label"] = "0%不参与"
        normalized["final_action"]["target"] = {}
    normalized["final_action"] = _carrier_strategy_effective_final_action(
        normalized["final_action"],
        normalized.get("sector_capital_carrier_strategy"),
    )
    normalized["layers"] = _build_sector_capital_preflight_layers(
        normalized.get("layers"),
        normalized.get("final_action"),
        normalized.get("source_payloads"),
    )
    if _preflight_layers_eliminate_final_target(
        normalized.get("layers"),
        normalized.get("final_action"),
    ):
        normalized["final_action"] = {
            "label": "0%不参与",
            "position_pct": 0,
            "target": {},
            "source": clean_text(normalized["final_action"].get("source"), "sector_capital_carrier_strategy"),
            "reason": "板块资金载体主样本已在价格行为或反方证据层被淘汰",
            "failure_conditions": ["价格行为或反方证据层已经否决主样本"],
        }
        normalized["layers"] = _build_sector_capital_preflight_layers(
            normalized.get("layers"),
            normalized.get("final_action"),
            normalized.get("source_payloads"),
        )
    normalized["layers"] = _sync_preflight_final_action_layer(
        normalized.get("layers"),
        normalized.get("final_action"),
    )
    normalized["decision_list"] = _normalize_decision_list(
        normalized.get("decision_list"),
        layers=normalized.get("layers"),
        final_action=normalized.get("final_action"),
    )
    normalized["idiot_index_review"] = _normalize_idiot_index_review(normalized.get("idiot_index_review"))
    normalized["tplus_rehearsal"] = _normalize_tplus_rehearsal(
        normalized.get("tplus_rehearsal"),
        layers=normalized.get("layers"),
        final_action=normalized.get("final_action"),
        source_payloads=normalized.get("source_payloads"),
    )
    if not _tplus_rehearsal_matches_final_action(
        normalized.get("tplus_rehearsal"),
        normalized.get("final_action"),
    ):
        normalized["tplus_rehearsal"] = _build_tplus_rehearsal(
            normalized.get("layers"),
            normalized.get("final_action"),
            source_payloads=normalized.get("source_payloads"),
        )
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
    if elimination:
        base_payload = dict(existing) if existing else {}
        base_payload.update(
            {
                "schema_version": SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION,
                "trade_date": clean_text(trade_date or base_payload.get("trade_date") or elimination.get("trade_date")),
                "variant": clean_text(variant or base_payload.get("variant") or elimination.get("variant") or "默认"),
                "derivation_contract": clean_text(
                    base_payload.get("derivation_contract"),
                    SECTOR_CAPITAL_PREFLIGHT_DERIVATION_CONTRACT,
                ),
                "source_artifact": clean_text(elimination.get("schema_version"), SCHEMA_VERSION),
                "source_payloads": source_payloads,
                "mermaid": clean_block_text(base_payload.get("mermaid")) or SECTOR_CAPITAL_PREFLIGHT_MERMAID,
                "final_action": final_action or _as_dict(base_payload.get("final_action")),
                "layers": _as_list(elimination.get("layers")),
            }
        )
        return _normalize_preflight_payload(base_payload)
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


def _mermaid_svg_id(value, prefix="mermaid"):
    text = clean_block_text(value)
    if not text:
        return f"{prefix}-empty"
    safe = []
    for ch in text:
        if ch.isalnum():
            safe.append(ch.lower())
        elif safe and safe[-1] != "-":
            safe.append("-")
    token = "".join(safe).strip("-")
    return f"{prefix}-{token[:48] or 'block'}"


def _json_for_html(payload):
    def _default(value):
        if isinstance(value, (_dt.date, _dt.datetime, _dt.time)):
            return value.isoformat()
        return str(value)

    text = json.dumps(
        payload if isinstance(payload, dict) else {},
        ensure_ascii=False,
        sort_keys=True,
        default=_default,
    )
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
    if clean_text(payload.get("schema_version")) == SECTOR_CAPITAL_PREFLIGHT_SCHEMA_VERSION:
        payload = _normalize_preflight_payload(payload)
    final_action = _as_dict(payload.get("final_action"))
    layers = _as_list(payload.get("layers"))
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_stock = stock_label(final_action.get("target")) if final_action.get("target") else "无执行对象"
    mermaid = clean_block_text(payload.get("mermaid")) or SECTOR_CAPITAL_PREFLIGHT_MERMAID
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
	    .preflight-flowchart {{
	      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin-bottom: 18px;
	      overflow: hidden;
	    }}
	    .flowchart-head {{
	      display: flex;
	      justify-content: space-between;
	      gap: 16px;
	      padding: 16px;
	      border-bottom: 1px solid var(--line);
	      background: #fbfcff;
	    }}
	    .flowchart-head h2 {{
	      margin: 0 0 6px;
	      font-size: 18px;
	      letter-spacing: 0;
	    }}
	    .flowchart-head p {{
	      margin: 0;
	      color: var(--muted);
	      font-size: 13px;
	    }}
	    .flowchart-head strong {{
	      align-self: flex-start;
	      flex: 0 0 auto;
	      border: 1px solid #e6c15c;
	      border-radius: 8px;
	      padding: 6px 10px;
	      color: var(--final);
	      background: var(--final-bg);
	      font-size: 13px;
	    }}
	    .flowchart-strip {{
	      display: flex;
	      align-items: stretch;
	      gap: 12px;
	      padding: 16px;
	      overflow-x: auto;
	      overscroll-behavior-inline: contain;
	      scroll-snap-type: x proximity;
	    }}
	    .flow-node {{
	      flex: 0 0 244px;
	      display: grid;
	      gap: 10px;
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 12px;
	      background: #fff;
	      scroll-snap-align: start;
	      min-height: 260px;
	      overflow-wrap: anywhere;
	    }}
	    .flow-node-top {{
	      display: grid;
	      gap: 4px;
	    }}
	    .flow-node-top span {{
	      color: var(--muted);
	      font-size: 12px;
	    }}
	    .flow-node-top strong {{
	      font-size: 16px;
	    }}
	    .flow-counts {{
	      display: grid;
	      grid-template-columns: repeat(3, 1fr);
	      gap: 6px;
	      margin: 0;
	    }}
	    .flow-counts div {{
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 6px;
	      text-align: center;
	      background: #f8fafc;
	    }}
	    .flow-counts dt {{
	      color: var(--muted);
	      font-size: 11px;
	    }}
	    .flow-counts dd {{
	      margin: 0;
	      font-size: 18px;
	      font-weight: 800;
	    }}
	    .flow-node p {{
	      margin: 0;
	      font-size: 12px;
	    }}
	    .flow-reason {{
	      border-top: 1px dashed var(--line);
	      padding-top: 8px;
	      color: #344054;
	    }}
	    .flow-final {{
	      border-top: 1px solid #e6c15c;
	      padding-top: 8px;
	      color: var(--final);
	    }}
	    .flow-arrow {{
	      flex: 0 0 26px;
	      display: grid;
	      place-items: center;
	      color: var(--muted);
	      font-size: 22px;
	      font-weight: 700;
	    }}
	    .flow-node.is-survived {{
	      border-color: #99d6ce;
	      background: var(--survived-bg);
	    }}
	    .flow-node.is-eliminated {{
	      border-color: #f5b5ae;
	      background: var(--eliminated-bg);
	    }}
	    .flow-node.is-final {{
	      border-color: #e6c15c;
	      background: var(--final-bg);
	    }}
	    .flow-node.is-empty {{
	      background: #f8fafc;
	      color: var(--muted);
	    }}
	    .mermaid-block {{
	      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin-bottom: 18px;
	      overflow: hidden;
	    }}
	    .mermaid-block summary {{
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 12px;
	      min-height: 46px;
	      padding: 12px 16px;
	      cursor: pointer;
	      list-style: none;
	      background: #fafbfe;
	      border-bottom: 1px solid var(--line);
	      font-weight: 700;
	    }}
	    .mermaid-block summary::-webkit-details-marker {{
	      display: none;
	    }}
	    .mermaid-block summary span {{
	      color: var(--muted);
	      font-size: 12px;
	      font-weight: 600;
	      text-align: right;
	    }}
	    .mermaid-block pre {{
	      margin: 0;
	      padding: 14px 16px;
	      overflow-x: auto;
	      white-space: pre;
	      font-size: 13px;
	      line-height: 1.5;
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
			      .flowchart-head {{ display: block; }}
			      .flowchart-head strong {{ display: inline-block; margin-top: 10px; }}
			      .flow-node {{ flex-basis: 232px; min-height: 240px; }}
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
		    {_render_preflight_flowchart(payload)}
		    <details class="mermaid-block" aria-label="Mermaid 文本复核">
		      <summary><strong>Mermaid 文本复核</strong><span>可复制到 Mermaid 工具复核</span></summary>
		      <pre><code>{_html_block(mermaid)}</code></pre>
		    </details>
		    {_render_key_paths(layers)}
			    <section class="tournament-flow" aria-label="选股淘汰赛流程">
		      {"".join(rendered_layers)}
		    </section>
  </main>
  <script type="application/json" id="elimination-payload">{_json_for_html(payload)}</script>
  {LOCAL_MERMAID_RENDERER_SCRIPT}
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
    final_entries = _entries_with_status(entries, "final_action")
    final_has_target = bool(final_entries and stock_payload(final_entries[0].get("stock")))
    if is_final and final_has_target:
        survivor_summary = _lane_summary_text(layer, _entries_with_status(entries, "final_action"), kind="output")
    if is_final and not final_has_target:
        survivor_summary = "无执行对象"
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
        {_render_lane_details(title="本层剩余", count=survivor_count, lane_class="round-lane survived-lane round-survivors", list_class="stock-list", list_html=_render_entry_cards((_entries_with_status(entries, "final_action") if is_final and final_has_target else _entries_with_status(entries, "survived")), empty_text="无执行对象" if is_final else "无"), open_by_default=True)}
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


def _join_rehearsal_list(value):
    items = _normalize_text_list(value)
    return "；".join(items) if items else "-"


def _render_preflight_tplus_rehearsal(rehearsal):
    rehearsal = _normalize_tplus_rehearsal(rehearsal)
    tplus1 = _as_dict(rehearsal.get("tplus1"))
    tplus2 = _as_dict(rehearsal.get("tplus2"))
    rows = [
        {
            "stage": "T0边界",
            "item": "事实边界",
            "projection": rehearsal.get("t0_boundary"),
            "basis": rehearsal.get("basis"),
            "action": rehearsal.get("review_boundary"),
        },
        {
            "stage": "T+1",
            "item": "市场情绪/周期",
            "projection": f"{clean_text(tplus1.get('market_emotion'), '-')} / {clean_text(tplus1.get('market_cycle'), '-')}",
            "basis": clean_text(tplus1.get("reason"), "-"),
            "action": clean_text(tplus1.get("action"), "-"),
        },
        {
            "stage": "T+1",
            "item": "板块情绪/周期",
            "projection": f"{clean_text(tplus1.get('sector_emotion'), '-')} / {clean_text(tplus1.get('sector_cycle'), '-')}",
            "basis": clean_text(tplus1.get("participation_qualification"), "-"),
            "action": _join_rehearsal_list(tplus1.get("buy_windows")),
        },
        {
            "stage": "T+1",
            "item": "确认/取消",
            "projection": _join_rehearsal_list(tplus1.get("confirmation_conditions")),
            "basis": _join_rehearsal_list(tplus1.get("cancellation_conditions")),
            "action": clean_text(tplus1.get("missed_entry_plan"), "-"),
        },
        {
            "stage": "T+2",
            "item": "市场情绪/周期",
            "projection": f"{clean_text(tplus2.get('market_emotion'), '-')} / {clean_text(tplus2.get('market_cycle'), '-')}",
            "basis": clean_text(tplus2.get("reason"), "-"),
            "action": clean_text(tplus2.get("action"), "-"),
        },
        {
            "stage": "T+2",
            "item": "板块情绪/周期",
            "projection": f"{clean_text(tplus2.get('sector_emotion'), '-')} / {clean_text(tplus2.get('sector_cycle'), '-')}",
            "basis": _join_rehearsal_list(tplus2.get("review_points")),
            "action": _join_rehearsal_list(tplus2.get("sell_windows")),
        },
    ]
    return _render_preflight_table(
        title="T0推演T+1/T+2交易环境",
        summary="前瞻预案；后验只用于批改",
        row_class="tplus-rehearsal-block",
        columns=(
            ("stage", "阶段"),
            ("item", "项目"),
            ("projection", "推演"),
            ("basis", "依据/反证"),
            ("action", "处理"),
        ),
        rows=rows,
    )


def _render_preflight_carrier_strategy(strategy):
    strategy = _as_dict(strategy)
    if not strategy:
        return ""
    primary = _as_dict(strategy.get("primary_candidate"))
    rows = []
    for stage in _as_list(strategy.get("stages")):
        stage = _as_dict(stage)
        survivors = [
            clean_text(_as_dict(item).get("label"))
            for item in _as_list(stage.get("survivors"))
            if clean_text(_as_dict(item).get("label"))
        ]
        eliminated = [
            clean_text(_as_dict(item).get("label"))
            for item in _as_list(stage.get("eliminated"))
            if clean_text(_as_dict(item).get("label"))
        ]
        first_reason = clean_text(
            _as_dict(_as_list(stage.get("survivors"))[0] if _as_list(stage.get("survivors")) else {}).get("reason")
            or _as_dict(_as_list(stage.get("eliminated"))[0] if _as_list(stage.get("eliminated")) else {}).get("reason")
            or strategy.get("action_reason"),
            "-",
        )
        rows.append(
            {
                "stage": clean_text(stage.get("title"), "复核层"),
                "input": stage.get("input_count", 0),
                "eliminated": f"{stage.get('eliminated_count', 0)}（{'、'.join(eliminated[:5]) or '-'}）",
                "survivor": f"{stage.get('survivor_count', 0)}（{'、'.join(survivors[:5]) or '-'}）",
                "reason": first_reason,
            }
        )
    if primary:
        rows.append(
            {
                "stage": "主样本",
                "input": "-",
                "eliminated": "-",
                "survivor": clean_text(primary.get("stock_label"), "-"),
                "reason": clean_text(primary.get("reason") or strategy.get("action_reason"), "-"),
            }
        )
    return _render_preflight_table(
        title="板块资金载体预案",
        summary="T0同源策略，只作差异复核，不新增第二个明日对象",
        row_class="carrier-strategy-block",
        columns=(
            ("stage", "环节"),
            ("input", "输入"),
            ("eliminated", "淘汰"),
            ("survivor", "剩余"),
            ("reason", "依据"),
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


def _flowchart_node_class(layer):
    layer = _as_dict(layer)
    layer_id = clean_text(layer.get("id"))
    input_count = _safe_int(layer.get("input_count"), 0)
    survivor_count = _safe_int(layer.get("survivor_count"), 0)
    eliminated_count = _safe_int(layer.get("eliminated_count"), 0)
    if layer_id == "final_action":
        return "is-final"
    if input_count <= 0 and survivor_count <= 0 and eliminated_count <= 0:
        return "is-empty"
    if survivor_count > 0:
        return "is-survived"
    return "is-eliminated"


def _flowchart_reason(layer):
    entries = _as_list(_as_dict(layer).get("entries"))
    eliminated = _entries_with_status(entries, "eliminated")
    if eliminated:
        return clean_text(eliminated[0].get("reason"), "本层条件未满足")
    final_entries = _entries_with_status(entries, "final_action")
    if final_entries:
        return clean_text(final_entries[0].get("reason"), "最终没有新增参与对象")
    note = clean_text(_as_dict(layer).get("note"))
    if note:
        return note
    if _safe_int(_as_dict(layer).get("input_count"), 0) <= 0:
        return "上一层没有剩余对象，本层不再重复淘汰"
    return "进入下一层复核"


def _render_preflight_flowchart(payload):
    payload = _normalize_preflight_payload(payload)
    layers = _as_list(payload.get("layers"))
    final_action = _as_dict(payload.get("final_action"))
    final_label = clean_text(final_action.get("label"), "0%不参与")
    final_target = stock_payload(final_action.get("target"))
    final_stock = stock_label(final_target) if final_target else "无执行对象"
    if not layers:
        layers = [
            {
                "id": "missing",
                "title": "数据不足",
                "input_count": 0,
                "eliminated_count": 0,
                "survivor_count": 0,
                "entries": [],
                "note": "数据不足，无法展示生成前复核细节",
            }
        ]
    nodes = []
    for index, layer in enumerate(layers, start=1):
        layer = _as_dict(layer)
        entries = _as_list(layer.get("entries"))
        layer_id = clean_text(layer.get("id"))
        is_final = layer_id == "final_action"
        input_count = _safe_int(layer.get("input_count"), 0)
        eliminated_count = _safe_int(layer.get("eliminated_count"), 0)
        survivor_count = _safe_int(layer.get("survivor_count"), 0)
        if is_final and not final_target:
            input_count = 0
        eliminated_preview = _stock_list_preview(_entries_with_status(entries, "eliminated"), limit=2)
        output_entries = _entries_with_status(entries, "final_action") if is_final and final_target else _entries_with_status(entries, "survived")
        output_preview = final_stock if is_final else _stock_list_preview(output_entries, limit=2)
        reason = _flowchart_reason(layer)
        final_text = ""
        if is_final:
            final_text = f"<p class=\"flow-final\"><b>最终对象：</b>{_html(final_stock)} ｜ <b>动作：</b>{_html(final_label)}</p>"
        nodes.append(
            """
            <article class="flow-node {klass}" data-layer-id="{layer_id}" role="listitem">
              <div class="flow-node-top">
                <span>第{index}层</span>
                <strong>{title}</strong>
              </div>
              <dl class="flow-counts">
                <div><dt>输入</dt><dd>{input_count}</dd></div>
                <div><dt>淘汰</dt><dd>{eliminated_count}</dd></div>
                <div><dt>剩余</dt><dd>{survivor_count}</dd></div>
              </dl>
              <p><b>淘汰：</b>{eliminated_preview}</p>
              <p><b>剩余：</b>{output_preview}</p>
              <p class="flow-reason"><b>关键理由：</b>{reason}</p>
              {final_text}
            </article>
            """.format(
                klass=_html(_flowchart_node_class(layer)),
                layer_id=_html(layer_id),
                index=_html(index),
                title=_html(layer.get("title")),
                input_count=_html(input_count),
                eliminated_count=_html(eliminated_count),
                survivor_count=_html(survivor_count),
                eliminated_preview=_html(eliminated_preview),
                output_preview=_html(output_preview),
                reason=_html(reason),
                final_text=final_text,
            )
        )
    flow_items = []
    for index, node in enumerate(nodes):
        if index:
            flow_items.append('<div class="flow-arrow" aria-hidden="true">→</div>')
        flow_items.append(node)
    mermaid_source = clean_block_text(payload.get("mermaid")) or SECTOR_CAPITAL_PREFLIGHT_MERMAID
    mermaid_id = _mermaid_svg_id(payload.get("trade_date"), prefix="sector-capital-preflight-mermaid")
    return f"""
    <section class="preflight-flowchart" aria-label="生成前复核流程图" data-flowchart-rendered="static">
      <div class="flowchart-head">
        <div>
          <h2>生成前复核流程图</h2>
          <p>先看板块资金路径，再看资金载体、价格行为、周期窗口和最终动作；下方折叠名单保留每层股票明细。</p>
        </div>
        <strong>{_html(final_label)}</strong>
      </div>
      <div class="flowchart-mermaid">
        <div class="flowchart-mermaid-head">
          <span>流程图渲染</span>
          <strong>可直接展开复核</strong>
        </div>
        <div class="flowchart-mermaid-body mermaid" id="{_html(mermaid_id)}">{_html(mermaid_source)}</div>
      </div>
      <div class="flowchart-strip" role="list">
        {"".join(flow_items)}
      </div>
    </section>
    """


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
    .flowchart-mermaid {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      margin-bottom: 18px;
      overflow: hidden;
    }}
    .flowchart-mermaid-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px 0;
      color: var(--muted);
      font-size: 12px;
    }}
    .flowchart-mermaid-head strong {{
      color: var(--final);
      font-size: 12px;
    }}
    .flowchart-mermaid-body {{
      padding: 10px 16px 14px;
      overflow-x: auto;
      background: #fff;
    }}
    .flowchart-mermaid-body svg {{
      max-width: 100%;
      height: auto;
    }}
	    .mermaid-block {{
	      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin-bottom: 18px;
	      overflow: hidden;
	    }}
	    .mermaid-block summary {{
	      display: flex;
	      align-items: center;
	      justify-content: space-between;
	      gap: 12px;
	      min-height: 46px;
	      padding: 12px 16px;
	      cursor: pointer;
	      list-style: none;
	      background: #fafbfe;
	      border-bottom: 1px solid var(--line);
	      font-weight: 700;
	    }}
	    .mermaid-block summary::-webkit-details-marker {{
	      display: none;
	    }}
	    .mermaid-block summary span {{
	      color: var(--muted);
	      font-size: 12px;
	      font-weight: 600;
	      text-align: right;
	    }}
	    .mermaid-block h2,
	    .flowchart-head h2 {{
	      margin: 0 0 6px;
	      font-size: 18px;
	      letter-spacing: 0;
	    }}
	    .flowchart-head p {{
	      margin: 0;
	      color: var(--muted);
	      font-size: 13px;
	    }}
	    .mermaid-block pre {{
	      margin: 0;
	      padding: 14px 16px;
	      overflow-x: auto;
	      white-space: pre;
	      font-size: 13px;
	      line-height: 1.5;
	    }}
	    .preflight-flowchart {{
	      background: var(--panel);
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      margin-bottom: 18px;
	      overflow: hidden;
	    }}
	    .flowchart-head {{
	      display: flex;
	      justify-content: space-between;
	      gap: 16px;
	      padding: 16px;
	      border-bottom: 1px solid var(--line);
	      background: #fbfcff;
	    }}
	    .flowchart-head strong {{
	      align-self: flex-start;
	      flex: 0 0 auto;
	      border: 1px solid #e6c15c;
	      border-radius: 8px;
	      padding: 6px 10px;
	      color: var(--final);
	      background: var(--final-bg);
	      font-size: 13px;
	    }}
    .flowchart-strip {{
      display: flex;
      align-items: stretch;
      gap: 12px;
      padding: 16px;
	      overflow-x: auto;
	      overscroll-behavior-inline: contain;
      scroll-snap-type: x proximity;
    }}
    .flowchart-mermaid {{
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    .flowchart-mermaid-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px 0;
      color: var(--muted);
      font-size: 12px;
    }}
    .flowchart-mermaid-head strong {{
      color: var(--final);
      font-size: 12px;
    }}
    .flowchart-mermaid-body {{
      padding: 10px 16px 14px;
      overflow-x: auto;
      background: #fff;
    }}
    .flowchart-mermaid-body svg {{
      max-width: 100%;
      height: auto;
    }}
    .flow-node {{
      flex: 0 0 244px;
      display: grid;
      gap: 10px;
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 12px;
	      background: #fff;
	      scroll-snap-align: start;
	      min-height: 260px;
	      overflow-wrap: anywhere;
	    }}
	    .flow-node-top {{
	      display: grid;
	      gap: 4px;
	    }}
	    .flow-node-top span {{
	      color: var(--muted);
	      font-size: 12px;
	    }}
	    .flow-node-top strong {{
	      font-size: 16px;
	    }}
	    .flow-counts {{
	      display: grid;
	      grid-template-columns: repeat(3, 1fr);
	      gap: 6px;
	      margin: 0;
	    }}
	    .flow-counts div {{
	      border: 1px solid var(--line);
	      border-radius: 8px;
	      padding: 6px;
	      text-align: center;
	      background: #f8fafc;
	    }}
	    .flow-counts dt {{
	      color: var(--muted);
	      font-size: 11px;
	    }}
	    .flow-counts dd {{
	      margin: 0;
	      font-size: 18px;
	      font-weight: 800;
	    }}
	    .flow-node p {{
	      margin: 0;
	      font-size: 12px;
	    }}
	    .flow-reason {{
	      border-top: 1px dashed var(--line);
	      padding-top: 8px;
	      color: #344054;
	    }}
	    .flow-final {{
	      border-top: 1px solid #e6c15c;
	      padding-top: 8px;
	      color: var(--final);
	    }}
	    .flow-arrow {{
	      flex: 0 0 26px;
	      display: grid;
	      place-items: center;
	      color: var(--muted);
	      font-size: 22px;
	      font-weight: 700;
	    }}
	    .flow-node.is-survived {{
	      border-color: #99d6ce;
	      background: var(--survived-bg);
	    }}
	    .flow-node.is-eliminated {{
	      border-color: #f5b5ae;
	      background: var(--eliminated-bg);
	    }}
	    .flow-node.is-final {{
	      border-color: #e6c15c;
	      background: var(--final-bg);
	    }}
	    .flow-node.is-empty {{
	      background: #f8fafc;
	      color: var(--muted);
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
	      .flowchart-head {{ display: block; }}
	      .flowchart-head strong {{ display: inline-block; margin-top: 10px; }}
	      .flow-node {{ flex-basis: 232px; min-height: 240px; }}
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
	    {_render_preflight_flowchart(payload)}
	    <div class="flowchart-mermaid">
	      <div class="flowchart-mermaid-head">
	        <span>Mermaid 渲染</span>
	        <strong>源码见下方折叠框</strong>
	      </div>
	      <div class="flowchart-mermaid-body mermaid" id="{_html(_mermaid_svg_id(payload.get('trade_date'), prefix='sector-capital-preflight-mermaid'))}">{_html_block(payload.get("mermaid"))}</div>
	    </div>
	    <details class="mermaid-block" aria-label="Mermaid 文本复核">
	      <summary><strong>Mermaid 文本复核</strong><span>可复制到 Mermaid 工具复核</span></summary>
	      <pre><code>{_html_block(payload.get("mermaid"))}</code></pre>
	    </details>
    {_render_preflight_tplus_rehearsal(payload.get("tplus_rehearsal"))}
    {_render_preflight_carrier_strategy(payload.get("sector_capital_carrier_strategy"))}
    {_render_preflight_decision_list(payload.get("decision_list"))}
    {_render_preflight_idiot_index_review(payload.get("idiot_index_review"))}
    <section class="tournament-flow" aria-label="板块资金扩散生成前复核层">
      {rendered_layers}
    </section>
  </main>
  <script type="application/json" id="sector-capital-preflight-payload">{_json_for_html(payload)}</script>
  {LOCAL_MERMAID_RENDERER_SCRIPT}
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
