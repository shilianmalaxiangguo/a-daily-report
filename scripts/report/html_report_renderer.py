from __future__ import annotations

import json
from html import escape
from pathlib import Path
from string import Template
from typing import Any

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.html_report_view import build_daily_report_view, missing_required_fact_labels


# Structured dashboard renderer built from normalized facts, not the Bear
# Markdown reader. Keep its checks separate from markdown_report_html.py.
class DailyReportHtmlDataMissingError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "daily_report_reader.html"


def _echarts_source_path() -> Path:
    return _repo_root() / ".generated" / "vendor" / "echarts" / "echarts.min.js"


def _echarts_loader_html() -> str:
    source_path = _echarts_source_path()
    if source_path.exists():
        source = source_path.read_text(encoding="utf-8").replace("</script", "<\\/script")
        return f"<script>\n{source}\n</script>"
    return '<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>'


def _html(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_for_html_script(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _target_label(value: Any) -> dict[str, Any] | str:
    target = _as_dict(value)
    name = target.get("stock_name") or target.get("name") or ""
    code = target.get("stock_code") or target.get("code") or target.get("id") or ""
    label = ""
    if name and code:
        label = f"{name}({code})"
    else:
        label = str(name or code or "")
    if not label:
        return ""
    return {"__html_cell_html": f'<code class="stock-ref">{_html(label)}</code>'}


def _styled_cell(text: Any, class_name: str) -> dict[str, Any]:
    return {"__html_cell_text": text, "__html_cell_class": class_name}


def _format_pct(value: Any) -> str:
    try:
        return "{:.2f}%".format(float(str(value).replace("%", "").strip()))
    except (TypeError, ValueError):
        return str(value if value is not None else "")


def _top50_share_cell(value: Any) -> dict[str, Any] | str:
    try:
        share = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return "待确认"
    if share < 18:
        return _styled_cell(_format_pct(share), "signal-cold")
    if share > 20:
        return _styled_cell(_format_pct(share), "signal-hot")
    return _format_pct(share)


def _breadth_count_cell(value: Any, *, direction: str) -> dict[str, Any] | str:
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        return "待确认"
    text = str(count)
    if direction == "up" and count > 4000:
        return _styled_cell(text, "signal-hot")
    if direction == "down" and count > 4000:
        return _styled_cell(text, "signal-cold")
    return text


def _cell(value: Any, *, attention: bool = False) -> str:
    class_names = []
    if attention:
        class_names.append("attention")
    if isinstance(value, dict) and "__html_cell_text" in value:
        class_name = str(value.get("__html_cell_class") or "").strip()
        if class_name:
            class_names.append(class_name)
        value = value.get("__html_cell_text")
    raw_html = None
    if isinstance(value, dict) and "__html_cell_html" in value:
        class_name = str(value.get("__html_cell_class") or "").strip()
        if class_name:
            class_names.append(class_name)
        raw_html = str(value.get("__html_cell_html") or "")
    class_attr = f' class="{" ".join(class_names)}"' if class_names else ""
    if raw_html is not None:
        return f"<td{class_attr}>{raw_html}</td>"
    return f"<td{class_attr}>{_html(value)}</td>"


def _table(headers: list[str], rows: list[list[Any]], *, attention_first_row: bool = False) -> str:
    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    table_class = "reader-table is-two-column" if len(headers) == 2 else "reader-table is-wide"
    if not rows:
        body = f'<tr><td colspan="{len(headers)}">暂无数据</td></tr>'
    else:
        body_rows = []
        for row_index, row in enumerate(rows):
            cells = "".join(
                _cell(value, attention=attention_first_row and row_index == 0 and cell_index == 1)
                for cell_index, value in enumerate(row)
            )
            body_rows.append(f"<tr>{cells}</tr>")
        body = "\n".join(body_rows)
    return f'<div class="{table_class}"><table><thead><tr>{header_html}</tr></thead><tbody>{body}</tbody></table></div>'


def _yes_no(value: Any) -> str:
    if value is True:
        return "参与"
    if value is False:
        return "不参与"
    return "待确认"


def _tomorrow_action_html(view: dict[str, Any]) -> str:
    action = _as_dict(view.get("tomorrow_action"))
    target_row_label = "观察对象" if action.get("can_participate") is False else "参与对象"
    target = action.get("primary_target") if action.get("can_participate") is not False else action.get("observation_target")
    rows = [
        ["明日新仓", action.get("position_state") or "待确认"],
        ["是否参与", _yes_no(action.get("can_participate"))],
        [target_row_label, _target_label(target) or "无"],
        ["参与窗口", action.get("participation_window") or "待确认"],
        ["动作摘要", action.get("action_summary") or "待确认"],
        ["取消条件", "；".join(str(item) for item in _as_list(action.get("cancel_conditions"))) or "待确认"],
        ["风险边界", action.get("risk_boundary") or "待确认"],
    ]
    return _table(["项目", "结论"], rows, attention_first_row=True)


def _market_spine_html(view: dict[str, Any]) -> str:
    market = _as_dict(view.get("market_spine"))
    rows = [
        ["市场适配", market.get("market_fit") or "待确认"],
        ["成交额", market.get("turnover_summary") or "待确认"],
        ["涨跌结构", market.get("breadth_summary") or "待确认"],
        ["市场阶段", market.get("market_phase") or "待确认"],
        ["指数结构", market.get("index_structure") or "待确认"],
        ["含义", market.get("why_it_matters") or "待确认"],
    ]
    if market.get("top50_turnover_share_pct") is not None:
        rows.insert(2, ["Top50成交额占比", _top50_share_cell(market.get("top50_turnover_share_pct"))])
    if market.get("up_count") is not None or market.get("down_count") is not None:
        rows.insert(3, ["上涨家数", _breadth_count_cell(market.get("up_count"), direction="up")])
        rows.insert(4, ["下跌家数", _breadth_count_cell(market.get("down_count"), direction="down")])
        rows = [row for row in rows if row[0] != "涨跌结构"]
    return _table(["项目", "内容"], rows)


def _mainline_html(view: dict[str, Any]) -> str:
    item = _as_dict(view.get("mainline_evidence"))
    rows = [
        ["周期主线", item.get("cycle_mainline") or item.get("confirmed_line") or "待确认"],
        ["当天主攻线", item.get("daily_attack_line") or item.get("confirmed_line") or "待确认"],
        ["两者关系", item.get("cycle_daily_relationship") or "待确认"],
        ["辅助方向", "；".join(str(value) for value in _as_list(item.get("supporting_lines"))) or "无"],
        ["攻击证据", "；".join(str(value) for value in _as_list(item.get("attack_evidence"))) or "待确认"],
        ["成交额占比", item.get("turnover_share") or "待确认"],
        ["资金流", item.get("fund_flow") or "待确认"],
        ["扩散", item.get("sector_breadth") or "待确认"],
        ["延续条件", "；".join(str(value) for value in _as_list(item.get("continuation_conditions"))) or "待确认"],
        ["失败条件", "；".join(str(value) for value in _as_list(item.get("failure_conditions"))) or "待确认"],
    ]
    return _table(["项目", "证据"], rows)


def _candidate_actions_html(view: dict[str, Any]) -> str:
    rows = []
    for item in _as_list(view.get("candidate_actions")):
        item = _as_dict(item)
        rows.append(
            [
                _target_label(item) or "待确认",
                item.get("role") or "待确认",
                item.get("buy_window") or item.get("participation_script") or "待确认",
                item.get("invalidation") or "待确认",
                item.get("missed_action") or "待确认",
            ]
        )
    return _table(["标的", "角色", "参与窗口", "认错线", "错过后动作"], rows)


def _reviews_html(view: dict[str, Any]) -> str:
    rows = []
    for item in _as_list(view.get("participation_reviews")):
        item = _as_dict(item)
        rows.append(
            [
                _target_label(item) or "待确认",
                item.get("review_status") or "等待更多事实",
                item.get("missed_action") or "",
            ]
        )
    if not rows:
        return '<p class="muted">暂无参与预演复盘。</p>'
    return _table(["标的", "复盘状态", "后续动作"], rows)


def _data_sources_html(view: dict[str, Any]) -> str:
    rows = []
    for item in _as_list(view.get("data_sources")):
        item = _as_dict(item)
        rows.append(
            [
                item.get("source_label") or "",
                item.get("source_policy") or "",
                item.get("trade_date") or "",
                item.get("source_date") or "",
                item.get("status") or "",
                item.get("warning") or "",
            ]
        )
    return _table(["来源", "策略", "交易日", "来源日期", "状态", "提示"], rows)


def _diagnostics_html(view: dict[str, Any]) -> str:
    diagnostics = _as_dict(view.get("diagnostics"))
    rows = [
        ["缺失关键事实", "；".join(str(value) for value in _as_list(diagnostics.get("missing_required_facts"))) or "无"],
        ["降级事实", "；".join(str(value) for value in _as_list(diagnostics.get("degraded_facts"))) or "无"],
        ["HTML路径", diagnostics.get("html_artifact_path") or ""],
    ]
    return _table(["项目", "结果"], rows)


def build_daily_report_html_path(
    target_date: str,
    *,
    root: str | Path | None = None,
    run_mode: str = LEDGER_MODE_FROZEN,
) -> Path:
    root_path = Path(root) if root is not None else _repo_root()
    reports_dir = root_path / "reports"
    suffix = ""
    if run_mode == LEDGER_MODE_REPLAY:
        reports_dir = reports_dir / "replay"
        suffix = "_replay"
    return reports_dir / f"{target_date}_A股日报_完整版{suffix}.html"


def render_daily_report_html(view: dict[str, Any]) -> str:
    meta = _as_dict(view.get("meta"))
    template = Template(_template_path().read_text(encoding="utf-8"))
    return template.safe_substitute(
        title=_html(meta.get("report_title") or "A股日报"),
        trade_date=_html(meta.get("trade_date") or ""),
        source=_html(meta.get("source") or ""),
        tomorrow_action=_tomorrow_action_html(view),
        market_spine=_market_spine_html(view),
        mainline_evidence=_mainline_html(view),
        candidate_actions=_candidate_actions_html(view),
        participation_reviews=_reviews_html(view),
        data_sources=_data_sources_html(view),
        diagnostics=_diagnostics_html(view),
        echarts_loader=_echarts_loader_html(),
        charts_payload=_json_for_html_script(_as_dict(view.get("charts"))),
    )


def save_daily_report_html(
    view: dict[str, Any],
    *,
    root: str | Path | None = None,
    overwrite_existing: bool = False,
) -> Path:
    missing = missing_required_fact_labels(view)
    if missing:
        raise DailyReportHtmlDataMissingError("HTML 日报关键数据不完整，停止生成：" + "、".join(missing))
    meta = _as_dict(view.get("meta"))
    path = build_daily_report_html_path(
        str(meta.get("trade_date") or ""),
        root=root,
        run_mode=str(meta.get("run_mode") or LEDGER_MODE_FROZEN),
    )
    diagnostics = view.setdefault("diagnostics", {})
    if isinstance(diagnostics, dict):
        diagnostics["html_artifact_path"] = str(path)
    if path.exists() and not overwrite_existing:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_daily_report_html(view), encoding="utf-8")
    return path


def save_daily_report_html_from_postgres(
    target_date: str,
    db_service: Any,
    *,
    root: str | Path | None = None,
    run_mode: str = LEDGER_MODE_FROZEN,
    overwrite_existing: bool = False,
) -> Path:
    view = build_daily_report_view(target_date, db_service, run_mode=run_mode)
    return save_daily_report_html(view, root=root, overwrite_existing=overwrite_existing)
