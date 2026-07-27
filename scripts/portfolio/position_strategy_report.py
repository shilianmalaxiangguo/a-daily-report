from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path

from report.execution_wording import (
    PREMARKET_50_TRIGGER_TEXT,
    PREMARKET_FULL_TRIGGER_TEXT,
    execution_clause_for_position_pct,
)
from report.position_context import (
    build_old_position_plan,
    existing_position_summary_from_context,
    is_tomorrow_empty_account_action,
    is_inferred_previous_report_position,
    normalize_inferred_previous_target_records,
    old_position_action_rows,
    position_fact_status,
    resolve_tomorrow_account_action,
)
from report.position_tier_contract import normalize_planned_position_tier_pct

LEDGER_MODE_REPLAY = "replay"


MARKET_SCENARIOS = [
    {
        "heading": "上证单边上升",
        "holding_action": "强于板块锚点的持仓继续持有；上升趋势：站上MA3并守MA7才允许持有或加仓；冲高后二次不过高、跌回均价线或先于指数翻绿时减仓。",
        "new_action": "只允许对大盘、板块、锚点、个股同时确认的极度看好目标按固定交易窗口条件执行。",
        "forbidden": "不因指数上涨扩大随机仓位，不把旧仓反弹当新机会买点。",
    },
    {
        "heading": "上证震荡",
        "holding_action": "旧仓不能主动走强就按弱处理；反抽优先降风险，避免在噪音里反复交易。",
        "new_action": "明日目标标的只等右侧放量突破并守住均价线。",
        "forbidden": "不把一分钟止跌当买点，不因候选池好看就临盘换仓。",
    },
    {
        "heading": "上证单边下跌",
        "holding_action": "持仓按防守线独立评估；下降趋势：MA20下方不主动开新仓；跌破计划防守线、反抽不过均价线或同步新低时执行卖出。",
        "new_action": "只保留明日目标标的的既定仓位；下一次V反或W底确认只用于检查前一晚预案。",
        "forbidden": "不因跌得多就买，不用新机会抵消旧仓亏损。",
    },
    {
        "heading": "上证M顶",
        "holding_action": "把冲高二次不过高当卖点；M顶：跌破MA7先降风险，跌破MA10认错；跌回均价线或破日内平台时降低隔夜暴露。",
        "new_action": "只保留明日目标标的的既定仓位；只有重新放量突破日内高点并站稳才执行。",
        "forbidden": "不把派发形态误判成进攻延续，不卖飞追回。",
    },
    {
        "heading": "上证W底",
        "holding_action": "W底：第二脚不破低点，站回MA3/MA7后才试；持仓先于指数修复时可继续观察，W失败则先降风险。",
        "new_action": "只执行前一晚既定仓位；第二脚确认、站回MA3/MA7、板块锚点止跌后才参与。",
        "forbidden": "不在第一脚低点提前猜底，不为了摊低成本新增仓位。",
    },
    {
        "heading": "上证V反",
        "holding_action": "已降风险的旧仓先看能否强于锚点；V反：先站回MA3，再看MA7是否收复；V反失败时继续防守。",
        "new_action": "只做右侧确认后的买入预演；昨晚已决定的对象在指数回0、板块止跌、目标承接同时成立时才执行，否则取消。",
        "forbidden": "不在第一脚急跌中补仓，不用可能V反取消防守线。",
    },
    {
        "heading": "上证A杀",
        "holding_action": "A杀：放量大跌超7%或同破MA7/MA10，先处理可卖风险仓位；执行条件单或防守线，取消幻想。",
        "new_action": "极端冰点只保留观察，等止跌后的二次确认；不是用新名单救旧仓。",
        "forbidden": "不抄底，不把高波动当机会，不把新名单当救命动作。",
    },
]

MA_EXECUTION_ANCHOR_TEXT = "MA3攻击线 / MA7分歧线 / MA10认错线 / MA20环境线"
MA_CONFIRMATION_TEXT = "成交量确认优先于均线形态"


def _clean_text(value, default="-"):
    text = str(value or "").strip()
    return text if text else default


def _normalize_code(value):
    text = str(value or "").strip()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:] if len(digits) >= 6 else text


def _parse_candidates_from_markdown(markdown_text):
    text = str(markdown_text or "").strip()
    if not text:
        return []
    try:
        from report.decision_ledger import parse_extreme_conviction_list_from_markdown
    except (ImportError, ModuleNotFoundError):
        return []
    return list(parse_extreme_conviction_list_from_markdown(text) or [])


def _source_report_allows_new_position(markdown_text):
    text = str(markdown_text or "")
    if not text.strip():
        return True
    no_new_markers = (
        "新开仓上限 | 0",
        "新开仓0手",
        "明日不新增参与",
        "不构成明日新增参与",
        "最终0%时只作观察样本",
        "只作观察样本",
        "不进入明日对象",
        "观察对象，不新增参与",
        "执行目标为无",
        "只记录承接是否修复，不新增参与",
        "最终不新增参与",
        "最终没有新增参与对象",
        "明日执行对象 | 无",
        "最终对象 | 无",
        "先处理旧仓，不新增参与",
    )
    return not any(marker in text for marker in no_new_markers)


def _extract_extreme_conviction_list(data, source_report_markdown=""):
    if source_report_markdown and _source_report_allows_new_position(source_report_markdown):
        markdown_candidates = _parse_candidates_from_markdown(source_report_markdown)
        if markdown_candidates:
            return markdown_candidates
    data = data or {}
    contexts = [
        data.get("execution_stage_context") or {},
        data.get("step2_bundle") or {},
    ]
    for context in contexts:
        rows = context.get("extreme_conviction_list") if isinstance(context, dict) else None
        if rows:
            return list(rows)
    artifacts = data.get("decision_ledger_artifacts") or {}
    snapshot = artifacts.get("snapshot") if isinstance(artifacts, dict) else {}
    cases = snapshot.get("cases") if isinstance(snapshot, dict) else None
    if cases:
        return [
            {
                "code": item.get("stock_code"),
                "name": item.get("stock_name"),
                "sector": (item.get("hypothesis") or {}).get("sector_candidate"),
                "conviction_reason": (item.get("hypothesis") or {}).get("stock_setup"),
                "planned_participation": item.get("planned_participation") or {},
            }
            for item in cases
        ]
    return []


def _candidate_name(item):
    return _clean_text(item.get("name") or item.get("stock_name") or item.get("股票"), "-")


def _candidate_code(item):
    return _normalize_code(item.get("code") or item.get("stock_code") or item.get("代码"))


def _candidate_plan(item):
    return item.get("planned_participation") or item.get("participation_script") or {}


def _as_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_extreme_ice_point(data):
    data = data or {}
    for context in (
        data,
        data.get("market_research_snapshot") or {},
        (data.get("market_research_snapshot") or {}).get("state_machine") or {},
    ):
        if isinstance(context, dict) and context.get("market_ice_point") is True:
            return True

    evidence = (
        ((data.get("market_research_snapshot") or {}).get("state_machine") or {}).get("market_performance_evidence")
        or ((data.get("execution_stage_context") or {}).get("market_research_snapshot") or {}).get("market_performance_evidence")
        or {}
    )
    funding = evidence.get("funding_activity") or {}
    new_high = evidence.get("new_high_attack") or {}
    top50_share = _as_float(funding.get("top50_share_pct"))
    new_high_pct = _as_float(new_high.get("all_a_share_pct"))
    return bool(top50_share is not None and top50_share < 18 and new_high_pct is not None and new_high_pct < 1)


def _format_recommended_position(plan):
    position_pct = _candidate_position_pct(plan)
    if position_pct >= 100:
        return "2x/100%满仓计划"
    if position_pct > 0:
        return "1x/50%半仓条件执行"
    return "0%不参与"


def _candidate_position_pct(plan):
    plan = plan if isinstance(plan, dict) else {}
    if "target_position_pct" in plan:
        try:
            return normalize_planned_position_tier_pct(plan.get("target_position_pct"))
        except (TypeError, ValueError):
            return 0
    attack_state = str(plan.get("attack_state") or "").strip().replace("％", "%")
    if attack_state in {"0", "0%", "50", "50%", "100", "100%"}:
        return int(attack_state.replace("%", ""))
    return 0


def _candidate_tier_label(plan):
    position_pct = _candidate_position_pct(plan)
    if position_pct >= 100:
        return "2x/100%满仓"
    if position_pct > 0:
        return "1x/50%半仓"
    return "0%不参与"


def _candidate_tier_execution_text(plan):
    position_pct = _candidate_position_pct(plan)
    if position_pct >= 100:
        return PREMARKET_FULL_TRIGGER_TEXT
    if position_pct > 0:
        return PREMARKET_50_TRIGGER_TEXT
    return execution_clause_for_position_pct(0)


def _format_account_new_entry(target, data):
    if not target:
        return "0%不参与"

    plan = _candidate_plan(target)
    position_pct = plan.get("target_position_pct")
    position_found = "target_position_pct" in plan
    if not position_found:
        for context in _current_report_contexts(data):
            workflow = context.get("selection_workflow") if isinstance(context, dict) else {}
            final = workflow.get("final") if isinstance(workflow, dict) and isinstance(workflow.get("final"), dict) else {}
            if "position_pct" in final:
                position_pct = final.get("position_pct")
                position_found = True
                break
            decision = context.get("position_decision") if isinstance(context, dict) else {}
            decision = decision if isinstance(decision, dict) else {}
            if "target_position_pct" in decision:
                position_pct = decision.get("target_position_pct")
                position_found = True
                break
    if not position_found:
        position_pct = _candidate_position_pct(plan)

    try:
        normalized_pct = normalize_planned_position_tier_pct(position_pct)
    except (TypeError, ValueError):
        normalized_pct = 0
    if normalized_pct <= 0:
        return "0%不参与"
    if normalized_pct >= 100:
        return "2x/100%核心进攻；B1先参与，B2确认后补到满仓"
    return "1x/50%半仓条件执行；B1参与权"


def _render_tomorrow_target_lines(candidates, data):
    lines = ["## 明日目标标的", ""]
    if _current_report_blocks_new_entry(data):
        lines.extend(["- 当前没有明日极度看好候选，明日不设目标标的。", ""])
        return lines
    if _is_extreme_ice_point(data):
        lines.extend(["- 当前属于极端冰点，明日极度看好全部降为观察，不设新买目标标的。", ""])
        return lines

    target = _active_tomorrow_target(candidates, data)
    if not target:
        lines.extend(["- 当前没有明日极度看好候选，明日不设目标标的。", ""])
        return lines
    plan = _candidate_plan(target)
    name = _candidate_name(target)
    code = _candidate_code(target) or "-"
    sector = _clean_text(target.get("sector") or target.get("所属板块"), "-")
    window = _clean_text(plan.get("buy_window") or plan.get("participation_window"), "09:50-10:10")
    position = _format_recommended_position(plan)
    execution_path = _format_candidate_execution_path(plan)
    fail_action = _format_candidate_fail_action(plan).replace("按0%不参与", "条件不满足回到0%")
    lines.extend(
        [
            "| 目标 | 代码 | 板块 | 推荐仓位 | 参与窗口 | 执行条件 | 失败动作 |",
            "|------|------|------|----------|----------|----------|----------|",
            f"| {name} | {code} | {sector} | {position} | {window} | {execution_path} | {fail_action} |",
            "",
            "- 大盘表现决定用桶、盆还是碗，不取消明日极度看好本身的推荐属性；条件不满足回到0%。",
            "",
        ]
    )
    return lines


def _active_tomorrow_target(candidates, data):
    if _current_report_blocks_new_entry(data):
        return None
    target = _extract_current_report_target(data)
    if target and not _is_extreme_ice_point(data):
        return target
    if candidates and not _is_extreme_ice_point(data):
        return candidates[0]
    return None


def _action_candidates(candidates, data):
    target = _active_tomorrow_target(candidates, data)
    if not target:
        return candidates
    if not candidates:
        return [target]
    if _target_key(target) != _target_key(candidates[0]):
        return [target]
    return candidates


def _position_label(position):
    name = _clean_text(position.get("name") or position.get("stock_name"), "")
    code = _normalize_code(position.get("code") or position.get("stock_code") or position.get("代码"))
    return f"{name}({code})" if name and code else name


def _position_names(positions):
    names = []
    for position in positions or []:
        name = _position_label(position)
        if name:
            names.append(name)
    return names


def _target_label(item):
    if not item:
        return "无"
    name = _candidate_name(item)
    code = _candidate_code(item)
    return f"{name}({code})" if code else name


def _target_key(item):
    if not item:
        return ""
    return _candidate_code(item) or _candidate_name(item)


_STOCK_REF_PATTERN = re.compile(r"([^，,\n|：:]+?)\((\d{6})\)")

_TARGET_PATTERNS = (
    re.compile(r"明日执行对象[：:| ]+([^|\n：:]+?)\((\d{6})\)"),
    re.compile(r"最终对象[：:| ]+明日执行对象[：: ]*([^|\n：:]+?)\((\d{6})\)"),
    re.compile(r"最终对象=([^，,\n|：:]+?)\((\d{6})\)"),
    re.compile(r"最终执行对象[：: ]+([^，,\n|：:]+?)\((\d{6})\)"),
)


def _stock_like_from_value(value):
    if not isinstance(value, dict):
        return {}
    source = value
    if isinstance(value.get("execution_object"), dict):
        source = value.get("execution_object") or {}
    stock = value.get("stock") if isinstance(value.get("stock"), dict) else {}
    name = _clean_text(
        source.get("name")
        or source.get("stock_name")
        or source.get("股票")
        or stock.get("name")
        or stock.get("stock_name"),
        "",
    )
    code = _candidate_code(source) or _candidate_code(stock)
    if not name and not code:
        return {}
    item = dict(source)
    item["name"] = name or code
    item["code"] = code
    sector = _clean_text(source.get("sector") or source.get("所属板块") or source.get("industry") or stock.get("sector"), "")
    if sector:
        item["sector"] = sector
    plan = source.get("planned_participation") if isinstance(source.get("planned_participation"), dict) else {}
    if not plan:
        plan = {
            key: source.get(key)
            for key in ("buy_window", "participation_window", "condition", "fallback_state", "target_position_pct")
            if source.get(key) not in (None, "")
        }
    if plan:
        item["planned_participation"] = plan
    return item


def _selection_workflow_final_target(workflow):
    if not isinstance(workflow, dict):
        return {}
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    target = _stock_like_from_value(final.get("execution_object") if isinstance(final.get("execution_object"), dict) else final)
    if not target:
        return {}
    try:
        position_pct = normalize_planned_position_tier_pct(final.get("position_pct"))
    except (TypeError, ValueError):
        return {}
    if position_pct <= 0:
        return {}
    plan = target.get("planned_participation") if isinstance(target.get("planned_participation"), dict) else {}
    plan = dict(plan)
    if final.get("fail_action") and not plan.get("fallback_state"):
        plan["fallback_state"] = str(final.get("fail_action"))
    plan["target_position_pct"] = position_pct
    if plan:
        target["planned_participation"] = plan
    return target


def _selection_workflow_blocks_new_entry(workflow):
    if not isinstance(workflow, dict):
        return False
    final = workflow.get("final") if isinstance(workflow.get("final"), dict) else {}
    if not final:
        return False
    if "position_pct" in final:
        try:
            position_pct = normalize_planned_position_tier_pct(final.get("position_pct"))
        except (TypeError, ValueError):
            return True
        if position_pct <= 0:
            return True
    action_text = _clean_text(final.get("action_text") or final.get("fail_action"), "")
    target = _stock_like_from_value(final.get("execution_object") if isinstance(final.get("execution_object"), dict) else final)
    return bool(not target and ("0%" in action_text or "不参与" in action_text or "无执行对象" in action_text))


def _final_resolution_blocks_new_entry(resolution):
    if not isinstance(resolution, dict) or not resolution:
        return False
    target = _stock_like_from_value(resolution.get("new_entry_target"))
    if target:
        return False
    decision = resolution.get("capital_priority_decision") if isinstance(resolution.get("capital_priority_decision"), dict) else {}
    priority = _clean_text(decision.get("capital_priority"), "")
    if priority in {"wait", "old_position_t"}:
        return True
    action_text = " ".join(
        str(value or "")
        for value in (
            resolution.get("action_text"),
            resolution.get("final_action"),
            resolution.get("reason"),
            decision.get("reason"),
        )
    )
    if "0%" in action_text or "不参与" in action_text or "无执行对象" in action_text:
        return True
    return any(
        key in resolution
        for key in (
            "new_entry_target",
            "display_target",
            "process_target",
            "watch_target",
            "existing_position_target",
            "capital_priority_decision",
        )
    )


def _current_report_contexts(data):
    data = data or {}
    return [
        data,
        data.get("execution_stage_context") if isinstance(data.get("execution_stage_context"), dict) else {},
        data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {},
    ]


def _current_report_blocks_new_entry(data):
    if is_tomorrow_empty_account_action(resolve_tomorrow_account_action(data)):
        return True
    for context in _current_report_contexts(data):
        if not isinstance(context, dict):
            continue
        if _final_resolution_blocks_new_entry(context.get("final_target_resolution")):
            return True
        if _selection_workflow_blocks_new_entry(context.get("selection_workflow")):
            return True
    return False


def _extract_current_report_target(data):
    contexts = _current_report_contexts(data)
    workflow_targets = [
        _selection_workflow_final_target(context.get("selection_workflow"))
        for context in contexts
        if isinstance(context, dict)
    ]
    workflow_target = next((target for target in workflow_targets if target), {})
    for context in contexts:
        resolution = context.get("final_target_resolution") if isinstance(context, dict) else {}
        if isinstance(resolution, dict):
            target = _stock_like_from_value(resolution.get("new_entry_target"))
            if target:
                if workflow_target and _target_key(workflow_target) == _target_key(target):
                    merged = dict(target)
                    workflow_plan = _candidate_plan(workflow_target)
                    if workflow_plan:
                        merged_plan = dict(_candidate_plan(target))
                        merged_plan.update(workflow_plan)
                        merged["planned_participation"] = merged_plan
                    return merged
                return target
            if _final_resolution_blocks_new_entry(resolution):
                return {}
        if _selection_workflow_blocks_new_entry(context.get("selection_workflow") if isinstance(context, dict) else {}):
            return {}
        for key in ("selected_position_candidate", "current_core_candidate"):
            target = _stock_like_from_value(context.get(key) if isinstance(context, dict) else {})
            if target:
                return target
    return workflow_target


def _extract_report_target_from_markdown(markdown_text):
    text = str(markdown_text or "")
    if not _source_report_allows_new_position(text):
        return {}
    for pattern in _TARGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return {"name": match.group(1).strip(), "code": match.group(2).strip()}
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        label = cells[0]
        value = " | ".join(cells[1:])
        if label in {"最终对象", "明日执行对象", "最终结果"} or "明日执行对象" in label:
            match = _STOCK_REF_PATTERN.search(value)
            if match:
                return {"name": match.group(1).strip(), "code": match.group(2).strip()}
    return {}


def _source_report_explicitly_ends_position(markdown_text):
    text = str(markdown_text or "")
    end_markers = (
        "| 旧仓事实 | 已确认无旧仓 |",
        "| 明日账户结果 | 明日空仓 |",
        "已确认今日空仓",
        "报告日：空仓",
    )
    return any(marker in text for marker in end_markers)


def _previous_trade_day(value):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    current = current - _dt.timedelta(days=1)
    while current.weekday() >= 5:
        current = current - _dt.timedelta(days=1)
    return current.isoformat()


def _postgres_only_runtime():
    return os.environ.get("A_DAILY_REPORT_POSTGRES_ONLY_RUNTIME") == "1"


def _load_report_day_data_from_postgres(target_date):
    try:
        from storage.database_service import DatabaseService
    except (ImportError, ModuleNotFoundError):
        return None
    service = DatabaseService.from_environment()
    if not service.is_postgres_backed():
        return None
    result = service.load_daily_report_snapshot(str(target_date or ""))
    if isinstance(result, dict) and "data" in result:
        result = result.get("data")
    return result if isinstance(result, dict) and result else None


def _report_artifact_paths(root, target_date, suffix):
    root = Path(root)
    paths = []
    if root.name == "replay":
        replay_suffix = suffix[:-3] + "_replay.md" if suffix.endswith(".md") else suffix + "_replay"
        paths.extend((root / f"{target_date}{replay_suffix}", root / f"{target_date}{suffix}"))
        paths.append(root.parent / f"{target_date}{suffix}")
    else:
        paths.append(root / f"{target_date}{suffix}")
    return list(dict.fromkeys(paths))


def _read_previous_report_target(target_date, output_root=None, *, prefer_postgres_history=False):
    previous = _previous_trade_day(target_date)
    if not previous:
        return {}
    immediate_previous = previous
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[2] / "reports"
    for _ in range(20):
        if prefer_postgres_history:
            previous_data = _load_report_day_data_from_postgres(previous)
            if not previous_data and _postgres_only_runtime():
                if previous == immediate_previous:
                    raise RuntimeError(f"{previous} PostgreSQL 前日报计划事实不可用，停止生成")
                break
            if previous_data:
                if is_tomorrow_empty_account_action(resolve_tomorrow_account_action(previous_data)):
                    return {
                        "source_report_date": previous,
                        "previous_report_no_target": True,
                        "previous_position_ended": True,
                    }
                target = _extract_current_report_target(previous_data)
                if target:
                    return {
                        "name": _candidate_name(target),
                        "code": _candidate_code(target),
                        "source_report_date": previous,
                    }
                account_state = _account_state_from_report_data(
                    previous_data,
                    f"postgresql.daily_report_facts/{previous}",
                )
                if account_state.get("state") == "target":
                    carried = dict(account_state.get("target") or {})
                    carried["source_report_date"] = previous
                    carried["carried_old_position"] = True
                    return carried
                if account_state.get("state") == "empty":
                    return {
                        "source_report_date": previous,
                        "previous_report_no_target": True,
                        "previous_position_ended": True,
                    }
        found_report_artifact = False
        explicit_position_end = False
        explicit_tomorrow_empty = False
        report_target = {}
        for suffix in ("_A股日报_执行摘要.md", "_A股日报_完整版.md"):
            for path in _report_artifact_paths(root, previous, suffix):
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                found_report_artifact = True
                if "| 明日账户结果 | 明日空仓 |" in text:
                    explicit_tomorrow_empty = True
                    continue
                target = _extract_report_target_from_markdown(text)
                if target and not report_target:
                    report_target = dict(target)
                    report_target["source_report_date"] = previous
                if _source_report_explicitly_ends_position(text):
                    explicit_position_end = True
        if explicit_tomorrow_empty:
            return {
                "source_report_date": previous,
                "previous_report_no_target": True,
                "previous_position_ended": True,
            }
        if report_target:
            return report_target
        if explicit_position_end:
            return {
                "source_report_date": previous,
                "previous_report_no_target": True,
                "previous_position_ended": True,
            }
        if found_report_artifact:
            account_state = _read_report_day_account_state(
                previous,
                output_root=root,
                prefer_postgres_history=False,
            )
            if account_state.get("state") == "target":
                carried = dict(account_state.get("target") or {})
                carried["source_report_date"] = previous
                carried["carried_old_position"] = True
                return carried
            if account_state.get("state") == "empty":
                return {
                    "source_report_date": previous,
                    "previous_report_no_target": True,
                    "previous_position_ended": True,
                }
        previous = _previous_trade_day(previous)
        if not previous:
            break
    return {"source_report_date": immediate_previous, "previous_report_no_target": True}


def _stock_ref_from_text(value):
    match = _STOCK_REF_PATTERN.search(str(value or ""))
    if not match:
        return {}
    return {"name": match.group(1).strip(), "code": match.group(2).strip()}


def _positions_from_existing_position_context(data):
    if not isinstance(data, dict):
        return []
    personal_context = data.get("personal_position_context")
    personal_context = personal_context if isinstance(personal_context, dict) else {}
    summary = personal_context.get("existing_position_summary")
    if not isinstance(summary, dict):
        summary = data.get("existing_position_summary")
    if not isinstance(summary, dict):
        return []
    summary = dict(summary)
    normalize_inferred_previous_target_records(summary)
    if summary.get("has_position") is not True:
        return []
    name = _clean_text(summary.get("name") or summary.get("stock_name"), "")
    code = _normalize_code(summary.get("code") or summary.get("stock_code"))
    if not (name or code):
        stock = _stock_ref_from_text(summary.get("summary"))
        name = stock.get("name", "")
        code = stock.get("code", "")
    if not (name or code):
        return []
    position_value = summary.get("position")
    if position_value in (None, ""):
        position_value = summary.get("position_pct")
    position = _as_float(position_value)
    item = {
        "name": name,
        "code": code,
        "position": position if position is not None else "待确认",
    }
    if summary.get("default_position_pct") not in (None, ""):
        item["default_position_pct"] = summary.get("default_position_pct")
    for key in (
        "position_source",
        "source_report_date",
        "inferred_from_previous_report",
        "has_position",
        "has_pending_position",
        "role",
        "holding_note",
    ):
        if summary.get(key) not in (None, ""):
            item[key] = summary.get(key)
    return [item]


def _is_empty_path_text(value):
    text = _clean_text(value, "")
    return text in {"", "-", "无", "空仓", "持仓未输入"}


def _account_state_unknown(source="", reason=""):
    return {"state": "unknown", "source": source, "reason": reason}


def _account_state_empty(source="", reason=""):
    return {"state": "empty", "source": source, "reason": reason}


def _account_state_target(target, source="", reason=""):
    if not target:
        return _account_state_unknown(source, reason)
    return {"state": "target", "target": target, "source": source, "reason": reason}


def _account_state_inferred(target, source="", reason=""):
    if not target:
        return _account_state_unknown(source, reason)
    return {"state": "inferred", "target": target, "source": source, "reason": reason}


def _is_empty_account_state_text(value):
    text = _clean_text(value, "")
    if text in {"", "-", "无", "空仓", "Ta+0 空仓"}:
        return True
    return any(
        marker in text
        for marker in (
            "报告日：空仓",
            "前一交易日空仓",
            "历史复盘日：空仓",
            "最远复盘日：空仓",
            "空仓等待",
            "无B1占用",
            "不生成B1/B2",
            "没有B1/B2",
            "没有Tb+0",
            "没有Tc+0",
        )
    )


def _is_unknown_account_state_text(value):
    text = _clean_text(value, "")
    return any(marker in text for marker in ("持仓未输入", "先确认旧仓", "旧仓事实不清", "未确认前不假定空仓"))


def _is_external_pending_account_state_text(value):
    text = _clean_text(value, "")
    return any(
        marker in text
        for marker in (
            "外部交易待核实",
            "外部交易记录待核实",
            "外部成交记录待确认",
        )
    )


def _old_timeline_state_is_active_for_target(value):
    text = _clean_text(value, "")
    if _is_empty_account_state_text(text) or _is_unknown_account_state_text(text):
        return False
    return any(
        marker in text
        for marker in (
            "上一份日报目标",
            "旧仓占用",
            "继续处理旧仓",
            "优先处理旧仓",
            "默认按昨晚预案",
            "明日目标",
            "Tb+0",
            "Tb+1",
            "Tc+0",
            "复核",
        )
    )


def _row_cells_from_markdown(text):
    rows = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped.replace("|", "").strip()) <= {"-"}:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells:
            rows.append(cells)
    return rows


def _date_from_day_order_cell(value):
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", str(value or "").strip())
    return match.group(1) if match else ""


def _read_new_day_order_account_state(rows, target_date, source=""):
    found_empty = False
    found_unknown = False
    for cells in rows:
        if len(cells) < 6 or cells[0] not in {"Ta", "Tb", "Tc", "Td", "Te"}:
            continue
        if _date_from_day_order_cell(cells[1]) != target_date:
            continue
        account_text = cells[2]
        target_text = cells[3]
        target = _stock_ref_from_text(f"{account_text} {target_text}")
        if target:
            if _is_external_pending_account_state_text(account_text):
                return _account_state_inferred(target, source, "day_order_row")
            return _account_state_target(target, source, "day_order_row")
        if _is_unknown_account_state_text(account_text):
            found_unknown = True
        if _is_empty_account_state_text(account_text):
            found_empty = True
    if found_empty:
        return _account_state_empty(source, "day_order_row")
    if found_unknown:
        return _account_state_unknown(source, "day_order_row")
    return _account_state_unknown(source, "day_order_row_missing")


def _read_old_timeline_account_state(rows, target_date, source=""):
    headers = rows[0] if rows else []
    if len(headers) < 3 or headers[0] != "轨道" or headers[1] != "标的":
        return _account_state_unknown(source, "old_timeline_missing")
    date_index = None
    for index, header in enumerate(headers[2:], 2):
        if _date_from_day_order_cell(header) == target_date:
            date_index = index
            break
    if date_index is None:
        return _account_state_unknown(source, "old_timeline_date_missing")

    found_empty = False
    found_unknown = False
    for cells in rows[1:]:
        if len(cells) <= date_index:
            continue
        lane = cells[0]
        target_cell = cells[1]
        day_state = cells[date_index]
        if _is_unknown_account_state_text(day_state) or _is_unknown_account_state_text(target_cell):
            found_unknown = True
        if _is_empty_account_state_text(day_state):
            found_empty = True
            continue
        target = _stock_ref_from_text(target_cell)
        if target and _old_timeline_state_is_active_for_target(day_state):
            if _is_external_pending_account_state_text(day_state):
                return _account_state_inferred(target, source, f"old_timeline:{lane}")
            return _account_state_target(target, source, f"old_timeline:{lane}")
    if found_empty:
        return _account_state_empty(source, "old_timeline")
    if found_unknown:
        return _account_state_unknown(source, "old_timeline")
    return _account_state_unknown(source, "old_timeline_no_fact")


def _read_old_position_account_state(text, source=""):
    value = str(text or "")
    external_pending = {}
    for line in value.splitlines():
        if not _is_external_pending_account_state_text(line):
            continue
        external_pending = _stock_ref_from_text(line)
        if external_pending:
            break
    if external_pending:
        return _account_state_inferred(
            external_pending,
            source,
            "old_position_text_external_pending",
        )
    for line in value.splitlines():
        if not any(
            marker in line for marker in ("前日报计划推定", "前日报计划对象", "上一份日报计划推定")
        ):
            continue
        inherited = _stock_ref_from_text(line)
        if inherited:
            return _account_state_target(inherited, source, "old_position_text_simulated_inherited")
    for pattern in (
        re.compile(r"旧仓处理\s*\|\s*持有([^，,\n|：:]+?)\((\d{6})\)"),
        re.compile(r"已有旧仓[：:]\s*持有([^，,\n|：:]+?)\((\d{6})\)"),
        re.compile(r"持有([^，,\n|：:]+?)\((\d{6})\).*?(?:旧仓|1x旧仓|仓位)"),
    ):
        match = pattern.search(value)
        if match:
            return _account_state_target(
                {"name": match.group(1).strip(), "code": match.group(2).strip()},
                source,
                "old_position_text",
            )
    return _account_state_unknown(source, "old_position_missing")


def _account_state_from_report_data(data, source=""):
    if not isinstance(data, dict) or not data:
        return _account_state_unknown(source, "postgres_report_missing")
    positions = _positions_from_existing_position_context(data)
    if positions:
        position = positions[0]
        target = {"name": position.get("name", ""), "code": position.get("code", "")}
        if position_fact_status(position, context_provided=True) == "pending_confirmation":
            return _account_state_inferred(
                target,
                source,
                "postgres_inferred_position_summary",
            )
        return _account_state_target(
            target,
            source,
            "postgres_existing_position_summary",
        )
    personal_context = data.get("personal_position_context")
    personal_context = personal_context if isinstance(personal_context, dict) else {}
    summary = personal_context.get("existing_position_summary")
    if not isinstance(summary, dict):
        summary = data.get("existing_position_summary")
    if data.get("position_context_provided") is True and not (
        isinstance(summary, dict) and summary.get("has_position")
    ):
        return _account_state_empty(source, "postgres_position_context")
    return _account_state_unknown(source, "postgres_position_context_missing")


def _read_report_day_account_state(target_date, output_root=None, *, prefer_postgres_history=False):
    day = str(target_date or "").strip()
    if not day:
        return _account_state_unknown("", "missing_date")
    if prefer_postgres_history:
        postgres_data = _load_report_day_data_from_postgres(day)
        if not postgres_data and _postgres_only_runtime():
            raise RuntimeError(f"{day} PostgreSQL 历史账户事实不可用，停止生成")
        if postgres_data:
            postgres_state = _account_state_from_report_data(
                postgres_data,
                f"postgresql.daily_report_facts/{day}",
            )
            if postgres_state.get("state") != "unknown" or _postgres_only_runtime():
                return postgres_state
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[2] / "reports"
    best_empty = None
    best_unknown = None
    for suffix in ("_持仓策略.md", "_A股日报_执行摘要.md", "_A股日报_完整版.md"):
        for path in _report_artifact_paths(root, day, suffix):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            source = str(path)
            rows = _row_cells_from_markdown(text)
            state = _read_old_position_account_state(text, source)
            if state.get("state") in {"target", "inferred"}:
                return state

            if rows and rows[0][:2] == ["轨道", "标的"]:
                state = _read_old_timeline_account_state(rows, day, source)
            else:
                state = _read_new_day_order_account_state(rows, day, source)
            if state.get("state") in {"target", "inferred"}:
                return state
            if state.get("state") == "empty" and best_empty is None:
                best_empty = state
            elif state.get("state") == "unknown" and best_unknown is None:
                best_unknown = state
    return best_empty or best_unknown or _account_state_unknown(str(root), "no_report_artifact")


def _read_report_day_path_target(target_date, output_root=None, *, prefer_postgres_history=False):
    state = _read_report_day_account_state(
        target_date,
        output_root=output_root,
        prefer_postgres_history=prefer_postgres_history,
    )
    return state.get("target") if state.get("state") == "target" else {}


def _weekday_cn(value):
    try:
        day = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    return ("周一", "周二", "周三", "周四", "周五", "周六", "周日")[day.weekday()]


def _add_trade_days(value, days):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    remaining = max(0, int(days))
    while remaining > 0:
        current = current + _dt.timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current.isoformat()


def _shift_trade_days(value, days):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    steps = abs(int(days))
    direction = 1 if int(days) >= 0 else -1
    while steps > 0:
        current = current + _dt.timedelta(days=direction)
        if current.weekday() < 5:
            steps -= 1
    return current.isoformat()


def _add_calendar_days(value, days):
    try:
        current = _dt.date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return ""
    current = current + _dt.timedelta(days=int(days))
    return current.isoformat()


def _date_weekday_label(value):
    text = str(value or "").strip()
    weekday = _weekday_cn(text)
    return f"{text}（{weekday}）" if weekday else text


def _render_day_order_timeline_lines(
    candidates,
    data,
    positions,
    target_date,
    previous_report_target=None,
    output_root=None,
    prefer_postgres_history=False,
):
    tomorrow_account_action = resolve_tomorrow_account_action(data)
    tomorrow_empty = is_tomorrow_empty_account_action(tomorrow_account_action)
    target = _active_tomorrow_target(candidates, data)
    if not target and isinstance(data, dict) and not _current_report_blocks_new_entry(data):
        source_report_markdown = data.get("source_report_markdown", "")
        if _source_report_allows_new_position(source_report_markdown):
            target = _extract_report_target_from_markdown(source_report_markdown)
    explicit_holding_names = _position_names(positions)
    holding_names = list(explicit_holding_names)
    holding_label = "、".join(holding_names)
    pending_holding = any(
        position_fact_status(position, context_provided=True) == "pending_confirmation"
        for position in positions or []
        if isinstance(position, dict)
    )
    previous_report_target = previous_report_target or {}
    previous_report_no_target = bool(previous_report_target.get("previous_report_no_target"))
    position_unknown = (
        isinstance(data, dict)
        and data.get("position_context_provided") is False
        and not holding_names
    )
    report_day = str(target_date or "").strip()
    ta_day = _shift_trade_days(report_day, -3)
    tb_day = _shift_trade_days(report_day, -2)
    tc_day = _shift_trade_days(report_day, -1)
    td_day = report_day
    te_day = _shift_trade_days(report_day, 1)
    ta_state = _read_report_day_account_state(
        ta_day,
        output_root=output_root,
        prefer_postgres_history=prefer_postgres_history,
    )
    tb_state = _read_report_day_account_state(
        tb_day,
        output_root=output_root,
        prefer_postgres_history=prefer_postgres_history,
    )
    tc_state = _read_report_day_account_state(
        tc_day,
        output_root=output_root,
        prefer_postgres_history=prefer_postgres_history,
    )
    ta_path = ta_state.get("target") if ta_state.get("state") in {"target", "inferred"} else {}
    tb_path = tb_state.get("target") if tb_state.get("state") in {"target", "inferred"} else {}
    tc_path = tc_state.get("target") if tc_state.get("state") in {"target", "inferred"} else {}
    ta_path_inferred = ta_state.get("state") == "inferred"
    tb_path_inferred = tb_state.get("state") == "inferred"
    tc_path_inferred = tc_state.get("state") == "inferred"
    ta_path_label = _target_label(ta_path) if ta_path else ""
    tb_path_label = _target_label(tb_path) if tb_path else ""
    tc_path_label = _target_label(tc_path) if tc_path else ""
    ta_label = "、".join(holding_names) if holding_names else ("持仓未输入" if position_unknown else "空仓")
    same_stock_target = bool(target and any(_matches_position(position, target) for position in positions or []))
    target_plan = _candidate_plan(target) if target else {}
    target_position_pct = _candidate_position_pct(target_plan) if target else 0
    position_summary = existing_position_summary_from_context(data)
    if not position_summary and positions:
        first_position = positions[0] if isinstance(positions[0], dict) else {}
        position_summary = dict(first_position)
        if "has_position" not in position_summary and "has_pending_position" not in position_summary:
            position_summary["has_position"] = True
    fact_status = position_fact_status(position_summary, context_provided=not position_unknown)
    if position_unknown and fact_status == "none":
        fact_status = "unknown"
    resolution = data.get("final_target_resolution") if isinstance(data, dict) and isinstance(data.get("final_target_resolution"), dict) else {}
    old_plan = resolution.get("old_position_plan") if isinstance(resolution.get("old_position_plan"), dict) else build_old_position_plan(position_summary)
    account_action_rows = old_position_action_rows(
        position_fact_status=fact_status,
        existing_position=position_summary,
        old_position_plan=old_plan,
        tomorrow_account_action=tomorrow_account_action,
    )
    if tomorrow_empty:
        te_account_text = "明日空仓"
        te_b12_text = "没有B1/B2；不买新股、不做T"
        te_action_text = "集合竞价卖清全部可卖旧仓；未全部成交继续尽早卖"
    elif position_unknown:
        te_account_text = "先确认是否已有旧仓"
        te_b12_text = "先确认是否已有B1；未确认不新增B2"
        te_action_text = "旧仓事实不清时不新增参与"
    elif pending_holding and not target:
        te_account_text = f"外部交易记录待核实（只核实记录）：{holding_label}"
        te_b12_text = "核实已成交才视为B1；未核实不新增B2"
        te_action_text = "0%不参与；只核实外部交易记录"
    elif pending_holding and same_stock_target:
        te_account_text = f"外部交易记录待核实：{holding_label}"
        te_b12_text = "核实已成交才视为B1；未核实不新增B2"
        te_action_text = "先核实成交事实；未核实成交不补B2"
    elif target and same_stock_target:
        te_account_text = "同股旧仓1x/50%先视为B1"
        te_b12_text = "已有1x/50%=B1参与权；强表态存活才加B2至2x/100%"
        te_action_text = "B2未确认不补；走弱先卖可卖旧仓并保持1x/50%或更低"
    elif target:
        te_account_text = "新目标单独看B1，不用旧仓亏损补仓"
        if target_position_pct >= 100:
            te_b12_text = "B1先到1x/50%；B2确认后补到2x/100%"
            te_action_text = "B1未变强不补B2；条件失败回到0%"
        else:
            te_b12_text = "B1参与权=1x/50%；本计划无B2"
            te_action_text = "B1条件不满足则取消参与；不追加B2"
    elif holding_names:
        te_account_text = "只处理旧仓风险"
        te_b12_text = "没有B2；只处理旧仓风险"
        te_action_text = "旧仓未修复则继续降风险"
    else:
        te_account_text = "空仓等待B1资格"
        te_b12_text = "没有B1/B2；保持空仓"
        te_action_text = "空仓等待下一份日报"
    if tc_path_label and tc_path_inferred:
        tc_account_text = f"上一交易日外部交易待核实：{tc_path_label}"
        tc_target_text = tc_path_label
        tc_b12_text = "未确认成交，不视为B1"
        tc_action_text = "进入Td先确认成交事实"
        td_account_text = "旧仓进入复核" if holding_names and not pending_holding else "外部交易待核实"
    elif tc_path_label:
        tc_account_text = f"上一交易日路径：{tc_path_label}"
        tc_target_text = tc_path_label
        tc_b12_text = "可能形成B1旧仓"
        tc_action_text = "进入Td复核，不临场补B2"
        td_account_text = "旧仓进入复核" if holding_names else "空仓"
    elif tc_state.get("state") == "empty":
        tc_account_text = "前一交易日空仓"
        tc_target_text = "-"
        tc_b12_text = "无B1占用"
        tc_action_text = "等待Td报告确认"
        td_account_text = "旧仓进入复核" if holding_names else "空仓"
    elif tc_state.get("state") == "unknown":
        tc_account_text = "前一交易日持仓未输入"
        tc_target_text = "-"
        tc_b12_text = "B1事实待确认"
        tc_action_text = "先确认账户事实，不从当前计划反推历史持仓"
        if holding_names:
            td_account_text = "外部交易待核实" if pending_holding else "旧仓进入复核"
        elif data.get("position_context_provided") is True and fact_status == "none":
            td_account_text = "空仓"
        else:
            td_account_text = "持仓未输入"
    elif explicit_holding_names:
        explicit_label = "、".join(explicit_holding_names)
        tc_account_text = f"上一交易日路径：{explicit_label}"
        tc_target_text = explicit_label
        tc_b12_text = "可能形成B1旧仓"
        tc_action_text = "进入Td复核，不临场补B2"
        td_account_text = "旧仓进入复核"
    elif position_unknown:
        tc_account_text = "前一交易日持仓未输入"
        tc_target_text = "-"
        tc_b12_text = "B1事实待确认"
        tc_action_text = "先确认旧仓，不假定空仓"
        td_account_text = "持仓未输入"
    elif previous_report_no_target:
        tc_account_text = "前一交易日空仓"
        tc_target_text = "-"
        tc_b12_text = "无B1占用"
        tc_action_text = "等待Td报告确认"
        td_account_text = "旧仓进入复核" if holding_names else "空仓"
    else:
        tc_account_text = "前一交易日空仓"
        tc_target_text = "-"
        tc_b12_text = "无B1占用"
        tc_action_text = "等待Td报告确认"
        td_account_text = "旧仓进入复核" if holding_names else "无旧仓"
    ta_account_text = (
        f"最远复盘日外部交易待核实：{ta_path_label}"
        if ta_path_label and ta_path_inferred
        else f"最远复盘日：{ta_path_label}"
        if ta_path_label
        else "最远复盘日：空仓"
        if ta_state.get("state") == "empty"
        else "最远复盘日：持仓未输入"
        if ta_state.get("state") == "unknown"
        else "最远复盘日"
    )
    tb_account_text = (
        f"历史复盘日外部交易待核实：{tb_path_label}"
        if tb_path_label and tb_path_inferred
        else f"历史复盘日：{tb_path_label}"
        if tb_path_label
        else "历史复盘日：空仓"
        if tb_state.get("state") == "empty"
        else "历史复盘日：持仓未输入"
        if tb_state.get("state") == "unknown"
        else "历史复盘日"
    )
    ta_target_text = ta_path_label or "-"
    tb_target_text = tb_path_label or "-"
    ta_b12_text = (
        "未确认成交，不视为B1"
        if ta_path_inferred
        else "历史路径校对"
        if ta_path_label
        else "B1事实待确认"
        if ta_state.get("state") == "unknown"
        else "不生成B1/B2"
    )
    tb_b12_text = (
        "未确认成交，不视为B1"
        if tb_path_inferred
        else "历史路径校对"
        if tb_path_label
        else "B1事实待确认"
        if tb_state.get("state") == "unknown"
        else "不生成B1/B2"
    )
    if holding_names:
        td_account_text = (
            f"外部交易记录待核实：{holding_label}"
            if pending_holding
            else f"旧仓进入复核：{holding_label}"
        )
    td_target_text = holding_label or "无"
    td_b12_text = (
        "只定Te的B1+B2预案，不下单；B2确认后才到2x/100%"
        if target and target_position_pct >= 100
        else "只定Te的B1预案，不下单；本计划无B2"
        if target
        else "Te不新增参与，B2取消"
    )
    td_action_text = "写清执行资格和取消条件" if target else "只观察，不新增参与"
    inferred_source_date = next(
        (
            str(position.get("source_report_date") or "").strip()
            for position in positions or []
            if isinstance(position, dict) and position.get("source_report_date")
        ),
        "",
    )
    previous_source_date = str(previous_report_target.get("source_report_date") or "").strip()
    explicit_current_empty = bool(
        isinstance(data, dict)
        and data.get("position_context_provided") is True
        and fact_status == "none"
    )
    if previous_source_date and not previous_report_no_target and not explicit_current_empty:
        previous_source_note = f"；上一份日报目标来源={previous_source_date}"
    elif inferred_source_date:
        previous_source_note = f"；前日报计划来源={inferred_source_date}"
    else:
        previous_source_note = ""
    te_target_text = (
        "无"
        if tomorrow_empty
        else _target_label(target)
        if target
        else "无"
        if pending_holding
        else (holding_label or "无")
    )

    if tomorrow_empty:
        te_note = "- Te执行明日空仓：不买新股、不做T；集合竞价卖清全部可卖旧仓，未清完继续尽早卖。"
    elif pending_holding and not target:
        te_note = "- Te只核实外部交易是否成立；未确认前保持0%不参与，不新增B2。"
    elif target:
        te_note = "- Te只执行前一晚已决定的参与或取消，不在盘中临时生成新买入决定。"
    elif holding_names:
        te_note = "- Te只处理已确认旧仓风险，不新增参与对象。"
    elif position_unknown:
        te_note = "- Te先核实账户事实；未确认前不新增参与。"
    else:
        te_note = "- Te保持0%不参与，等待下一份日报重新评估。"

    return [
        "| 日序 | 日期 | 账户位置 | 执行目标 | B1/B2执行层 | 动作 |",
        "|------|------|----------|----------|-------------|------|",
        f"| Ta | {_date_weekday_label(ta_day)} | {ta_account_text} | {ta_target_text} | {ta_b12_text} | 只作路径校对，不改变Te动作 |",
        f"| Tb | {_date_weekday_label(tb_day)} | {tb_account_text} | {tb_target_text} | {tb_b12_text} | 只作路径校对，不改变Te动作 |",
        f"| Tc | {_date_weekday_label(tc_day)} | {tc_account_text} | {tc_target_text} | {tc_b12_text} | {tc_action_text} |",
        f"| Td | {_date_weekday_label(td_day)} | 报告日：{td_account_text}{previous_source_note} | {td_target_text} | {td_b12_text} | {td_action_text} |",
        f"| Te | {_date_weekday_label(te_day)} | {te_account_text} | {te_target_text} | {te_b12_text} | {te_action_text} |",
        "",
        "- 顶部账户日序表按近5个交易日展示：Ta最远，Tb/Tc为前两段，Td是报告日，Te是明日执行日。",
        "- B1是1x/50%参与权；只有2x/100%计划或同股T确认路径才有B2，B2不确认就不补。",
        te_note,
        "",
        "| 明日账户动作 | 结论 |",
        "|--------------|------|",
        *(["| 明日账户结果 | 明日空仓 |"] if tomorrow_empty else []),
        f"| 明日新仓 | {_format_account_new_entry(target, data)} |",
        *[
            f"| {label} | {account_action_rows[label]} |"
            for label in ("旧仓事实", "旧仓判断", "旧仓动作", "收盘目标仓位")
        ],
        "",
    ]


def _item_name(item):
    return _clean_text(item.get("name") or item.get("stock_name") or item.get("股票"), "")


def _item_code(item):
    return _normalize_code(item.get("code") or item.get("stock_code") or item.get("代码"))


def _matches_position(position, item):
    name = _clean_text(position.get("name"), "")
    code = _normalize_code(position.get("code") or position.get("stock_code"))
    if name and name == _item_name(item):
        return True
    if code and code == _item_code(item):
        return True
    return False


def _holding_membership(position, candidates):
    for candidate in candidates:
        if _matches_position(position, candidate):
            return True
    return False


def _get_nested(data, path):
    current = data or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_tracking_memory_items(data):
    status_paths = [
        ("tracking_memory_status",),
        ("execution_stage_context", "tracking_memory_status"),
        ("market_research_snapshot", "tracking_memory_status"),
        ("market_research_snapshot", "observation", "tracking_memory_status"),
        ("report_context", "tracking_memory_status"),
        ("strategy_tracking_context", "tracking_memory_status"),
    ]
    item_keys = [
        "today_validated_items",
        "validated_items",
        "promoted_items",
        "today_tentative_items",
        "tentative_items",
        "new_items",
        "total_items",
    ]
    items = []
    seen = set()
    for path in status_paths:
        status = _get_nested(data, path)
        if not isinstance(status, dict):
            continue
        for key in item_keys:
            for item in status.get(key) or []:
                if not isinstance(item, dict):
                    continue
                marker = (_item_code(item), _item_name(item), str(item.get("last_seen_date") or ""))
                if marker in seen:
                    continue
                seen.add(marker)
                items.append(item)
    return items


def _parse_int(value, default=999):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _is_prior_high_inertia_item(item):
    days_since_seen = _parse_int(item.get("days_since_seen"), default=999)
    if days_since_seen > 1:
        return False
    combined = " ".join(
        str(value or "")
        for value in [
            item.get("status"),
            item.get("follow_state"),
            item.get("last_reason"),
            " ".join(item.get("sources") or []),
        ]
    )
    high_inertia_markers = (
        "高惯性",
        "T字板",
        "涨停",
        "连板",
        "分歧转一致",
        "强异动",
        "板块前排",
        "明日可能加速",
        "观察竞价",
        "回封",
        "打板",
        "leader_memory",
    )
    return any(marker in combined for marker in high_inertia_markers)


def _holding_identity(position, candidates, tracking_items):
    if _holding_membership(position, candidates):
        return "是", "current_extreme"
    for item in tracking_items or []:
        if _matches_position(position, item) and _is_prior_high_inertia_item(item):
            return "昨日高惯性回看", "prior_high_inertia"
    return "否", "ordinary"


def _holding_identity_action(identity_kind):
    if identity_kind == "current_extreme":
        return "当前仍在明日极度看好；先按原参与脚本验证强弱，强于锚点才持有，走弱仍按旧仓风控处理。"
    if identity_kind == "prior_high_inertia":
        return (
            "昨日高惯性/过程观察样本，保留延续观察资格，但不是当前新买按钮；"
            "开盘强攻路径只看急拉、几千万级大单净流入和封板/回封质量，"
            "10点路径看09:50-10:10筹码交换后不再下杀，并站回分时黄线/0轴；"
            "确认失败就降为普通旧仓风控，不为摊低成本加仓。"
        )
    return "不享受极度看好身份；只按旧仓失效、防守线和大盘剧本处理。"


def _format_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{number:.3f}".rstrip("0").rstrip(".")


def _format_lots(value):
    text = _format_number(value)
    return f"{text}手" if text else ""


def _format_holding_position_text(position):
    def _join_trade_context(base):
        parts = [base] if base else []
        if position.get("trade_action") == "做T":
            buy_text = _format_lots(position.get("buy_lots"))
            sell_text = _format_lots(position.get("sell_lots"))
            trade_parts = []
            if buy_text:
                trade_parts.append(f"买入{buy_text}")
            if sell_text:
                trade_parts.append(f"卖出{sell_text}")
            parts.append(f"今日做T{'、'.join(trade_parts)}" if trade_parts else "今日做T")
        note = _clean_text(position.get("holding_note"), "")
        if note:
            parts.append(note)
        return "，".join(parts) if parts else "-"

    pct = position.get("position", position.get("position_pct", None))
    if isinstance(pct, (int, float)):
        return _join_trade_context(f"{pct:.1f}%")
    if pct not in (None, ""):
        return _join_trade_context(_clean_text(pct, "-"))
    shares = position.get("shares")
    if not shares and position.get("lots") not in (None, ""):
        shares = int(float(position.get("lots")) * 100)
    lots_text = _format_lots(position.get("lots"))
    parts = []
    if lots_text:
        parts.append(lots_text)
    if shares:
        parts.append(f"{shares}股")
    base = "/".join(parts)
    return _join_trade_context(base)


def _render_holding_rows(positions, candidates, tracking_items, scenario, *, position_unknown=False):
    if position_unknown:
        return [
            "| 持仓未输入 | 待确认 | 待确认 | "
            "先核对实际持仓；未确认前不生成旧仓卖出或持有动作 | 先确认账户事实 |"
        ]
    rows = []
    for position in positions or []:
        name = _clean_text(position.get("name") or position.get("stock_name"), "-")
        if position_fact_status(position, context_provided=True) == "pending_confirmation":
            rows.append(
                f"| {name}（外部交易待核实） | 0x | 否 | "
                "只核实外部交易记录；未核实成交前不执行持仓卖出或加仓动作 | "
                "外部交易待核实，未核实成交不视为B1或旧仓 |"
            )
            continue
        pct_text = _format_holding_position_text(position)
        identity, identity_kind = _holding_identity(position, candidates, tracking_items)
        action = _holding_identity_action(identity_kind)
        rows.append(f"| {name} | {pct_text} | {identity} | {scenario['holding_action']} | {action} |")
    if rows:
        return rows
    return ["| - | - | - | 今日空仓，无旧仓处理 | 无旧仓处理 |"]


def _format_candidate_execution_path(plan):
    entry_timing = _clean_text(plan.get("entry_timing"), "")
    parts = []
    if entry_timing == "open_core" or str(plan.get("buy_window") or "").startswith("09:30"):
        parts.append("09:30-09:35 开盘强攻/打板入口")
    parts.append("09:50-10:10 筹码交换/分时黄线或0轴确认入口")
    intraday_cross = _clean_text(
        plan.get("intraday_average_line_cross_probe"),
        "09:50-10:10价格与分时黄色均价线交叉并形成金叉，且上穿后不快速跌回黄线下方",
    )
    zero_axis = _clean_text(
        plan.get("zero_axis_reclaim_probe"),
        "水下强势修复到0轴，0轴附近不再放量回落，才算资金重新表态",
    )
    daily_ma = _clean_text(
        plan.get("daily_ma_entry_probe"),
        "逻辑确认后再看MA3/MA7/MA10/MA20：MA3=攻击线，MA7=分歧线，MA10=认错线，MA20=环境线；MA不是买入理由，只是执行锚点和失效参考，仍要叠加分时承接",
    )
    parts.append(intraday_cross)
    parts.append(zero_axis)
    parts.append(daily_ma)
    position_pct = _candidate_position_pct(plan)
    if position_pct >= 100:
        parts.append("B1先执行到1x/50%；确认成立后B2再补到2x/100%")
    elif position_pct > 0:
        parts.append("B1只执行一笔到1x/50%；本计划不追加B2")
    else:
        parts.append("0%不参与，只观察或处理旧仓")
    return "；".join(parts)


def _format_candidate_fail_action(plan):
    fail_action = _clean_text(
        plan.get("cancellation") or plan.get("fallback_state") or "任一确认失败按0%不参与",
        "任一确认失败按0%不参与",
    )
    guard = "不把价格更低本身当买点；10点仍走弱或承接继续扩散，按0%不参与"
    if guard in fail_action:
        return fail_action
    return f"{fail_action}；{guard}"


def _append_execution_path(action_text, execution_path):
    base = _clean_text(action_text, "").rstrip("。；; ")
    if not base:
        return f"执行路径：{execution_path}"
    return f"{base}；执行路径：{execution_path}"


def _render_candidate_rows(candidates, scenario, *, new_entry_blocked=False):
    rows = []
    for item in candidates or []:
        plan = _candidate_plan(item)
        name = _candidate_name(item)
        code = _candidate_code(item) or "-"
        sector = _clean_text(item.get("sector") or item.get("所属板块"), "-")
        window = (
            "无新增参与窗口"
            if new_entry_blocked
            else _clean_text(plan.get("buy_window") or plan.get("participation_window"), "按日报参与窗口")
        )
        attack_state = "0%不参与" if new_entry_blocked else _candidate_tier_label(plan)
        reason = _clean_text(item.get("conviction_reason") or item.get("reason"), "-")
        execution_path = _format_candidate_execution_path(plan)
        new_action = (
            "只作过程回放，不新增参与"
            if new_entry_blocked
            else _append_execution_path(
                f"{scenario['new_action'].rstrip('。')}；{_candidate_tier_execution_text(plan)}",
                execution_path,
            )
        )
        fail_action = "不参与" if new_entry_blocked else _format_candidate_fail_action(plan)
        rows.append(
            f"| {name} | {code} | {sector} | {window} | {attack_state} | {new_action} | {fail_action} | {reason} |"
        )
    if rows:
        return rows
    return ["| - | - | - | - | - | 当前无明日极度看好候选 | 不参与 | - |"]


def render_position_strategy_report(
    data,
    target_date,
    positions,
    source_report_markdown="",
    output_root=None,
    *,
    prefer_postgres_history=False,
):
    data = dict(data or {})
    effective_positions = list(positions or [])
    if not effective_positions:
        effective_positions = _positions_from_existing_position_context(data)
    if source_report_markdown:
        data.setdefault("source_report_markdown", source_report_markdown)
    position_unknown = data.get("position_context_provided") is False and not _position_names(effective_positions)
    candidates = _extract_extreme_conviction_list(data, source_report_markdown=source_report_markdown)
    action_candidates = _action_candidates(candidates, data)
    new_entry_blocked = _current_report_blocks_new_entry(data)
    tracking_items = _extract_tracking_memory_items(data)
    previous_report_target = _read_previous_report_target(
        target_date,
        output_root=output_root,
        prefer_postgres_history=prefer_postgres_history,
    )
    lines = [
        *_render_day_order_timeline_lines(
            candidates,
            data,
            effective_positions,
            target_date,
            previous_report_target=previous_report_target,
            output_root=output_root,
            prefer_postgres_history=prefer_postgres_history,
        ),
        f"# {target_date} 持仓策略",
        "",
        "## 核心原则",
        "",
        "- 卖出处理和买入处理分开判断。",
        "- 不因新机会而处理旧仓，也不因旧仓处理结果强行开启新仓。",
        "- 明日极度看好是推荐面，不是无条件买入按钮；先选明日目标标的，再用大盘、板块、锚点、个股确认决定容器大小。",
        f"- 买卖点执行锚点：{MA_EXECUTION_ANCHOR_TEXT}；{MA_CONFIRMATION_TEXT}。",
        "- 先有板块/资金/承接资格，再看均线执行锚点。",
        "- 上午做超短主动性，下午做短线确认。",
        "- 0%不参与不是没有策略；不开新仓时也按MA3/MA7/MA10/MA20管理旧仓和观察对象。",
        "",
    ]
    lines.extend(_render_tomorrow_target_lines(candidates, data))
    for scenario in MARKET_SCENARIOS:
        lines.extend(
            [
                f"# {scenario['heading']}",
                "",
                "## 持仓处理",
                "",
                "| 持仓 | 仓位 | 是否在明日极度看好 | 剧本下卖出/持有动作 | 个股身份处理 |",
                "|------|------|--------------------|----------------------|--------------|",
                *_render_holding_rows(
                    effective_positions,
                    candidates,
                    tracking_items,
                    scenario,
                    position_unknown=position_unknown,
                ),
                "",
                "## 新机会处理",
                "",
                "| 候选 | 代码 | 板块 | 参与窗口 | 仓位三态 | 剧本下买入动作 | 不满足怎么办 | 理由 |",
                "|------|------|------|----------|----------|----------------|--------------|------|",
                *_render_candidate_rows(action_candidates, scenario, new_entry_blocked=new_entry_blocked),
                "",
                "## 禁止动作",
                "",
                f"- {scenario['forbidden']}",
                "- 旧仓处理和新机会处理必须分开记录，不能合并成换仓指令。",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def get_position_strategy_output_path(target_date, mode="frozen", output_root=None):
    root = Path(output_root) if output_root else Path(__file__).resolve().parents[2] / "reports"
    if mode == LEDGER_MODE_REPLAY:
        root = root / "replay"
    root.mkdir(parents=True, exist_ok=True)
    suffix = "_replay" if mode == LEDGER_MODE_REPLAY else ""
    return str(root / f"{target_date}_持仓策略{suffix}.md")


def save_position_strategy_report(report_text, target_date, mode="frozen", output_root=None):
    path = Path(get_position_strategy_output_path(target_date, mode=mode, output_root=output_root))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    print(f"✅ 持仓策略已保存: {path}")
    return str(path)


__all__ = [
    "MARKET_SCENARIOS",
    "get_position_strategy_output_path",
    "render_position_strategy_report",
    "save_position_strategy_report",
]
