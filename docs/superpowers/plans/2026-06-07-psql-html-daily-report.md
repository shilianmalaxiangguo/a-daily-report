# PSQL 驱动 HTML 日报实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 按已批准规格实现 PSQL 细表驱动的每日 HTML 日报阅读产物，不新增每日完整 JSON 附属文件。

**实现思路：** 先建立 `DailyReportView` 查询层，从 `DatabaseService` 读取目标交易日的 PSQL 事实并组装轻量阅读对象。再用独立 HTML 渲染器和模板输出 Bear 阅读器式页面。最后在日报入口保存 Markdown 后尝试生成 HTML，PSQL 不可用或关键事实缺失时只记录原因，不影响 Markdown。

**技术栈：** Python 3.14（固定使用 `.generated/venv-py314/bin/python3.14`）、`unittest`、标准库 `html.escape`、`string.Template`、现有 `DatabaseService` / `daily_report_render` 输出路径规则。

---

## 文件结构

- 新建 `scripts/report/html_report_view.py`
  - 职责：从 PSQL 查询结果组装 `DailyReportView`。
  - 导出：
    - `build_daily_report_view(target_date, db_service, *, run_mode="frozen")`
    - `daily_report_view_has_required_facts(view)`
    - `missing_required_fact_labels(view)`

- 新建 `scripts/report/html_report_renderer.py`
  - 职责：把 `DailyReportView` 渲染并保存为 HTML。
  - 导出：
    - `build_daily_report_html_path(target_date, *, root=None, run_mode="frozen")`
    - `render_daily_report_html(view)`
    - `save_daily_report_html(view, *, root=None, overwrite_existing=False)`
    - `save_daily_report_html_from_postgres(target_date, db_service, *, root=None, run_mode="frozen")`

- 新建 `scripts/templates/daily_report_reader.html`
  - 职责：Bear 阅读器式白/灰/黑/红 HTML 模板。

- 新建 `tests/test_daily_report_html_view.py`
  - 职责：验证 PSQL 阅读视图组装、缺失事实、无每日完整 JSON 输出。

- 新建 `tests/test_daily_report_html_renderer.py`
  - 职责：验证 HTML 转义、路径、replay 后缀、视觉 token、缺失事实停止保存。

- 新建 `tests/test_daily_report_entry_html_output.py`
  - 职责：验证日报入口在 Markdown 保存后尝试保存 HTML，且 HTML 失败不影响 Markdown。

- 修改 `scripts/daily_report_entry_demo.py`
  - 职责：增加最小 HTML 保存接入点。
  - 禁止：不改交易判断逻辑，不重构日报入口，不新增每日完整 JSON。

## 任务 1：PSQL 阅读视图契约

**文件：**
- 新建：`scripts/report/html_report_view.py`
- 测试：`tests/test_daily_report_html_view.py`

- [ ] **步骤 1：先写失败测试**

新建 `tests/test_daily_report_html_view.py`：

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report.html_report_view import (
    build_daily_report_view,
    daily_report_view_has_required_facts,
    missing_required_fact_labels,
)


class FakePostgresDailyReportService:
    def __init__(self, *, snapshot=None, mentions=None, coverage=None):
        self.snapshot = snapshot or {}
        self.mentions = mentions or []
        self.coverage = coverage or {
            "tables": {
                "daily_report_fact_fields": {"target_count": 8, "max_trade_date": "2026-06-05"},
                "sector_attack_evidence_daily": {"target_count": 2, "max_trade_date": "2026-06-05"},
            }
        }
        self.loaded_dates = []

    def is_postgres_backed(self):
        return True

    def load_daily_report_snapshot(self, trade_date):
        self.loaded_dates.append(trade_date)
        return {
            "source": f"postgresql://daily-report-facts/{trade_date}",
            "field_count": 8 if self.snapshot else 0,
            "target_field_count": 8 if self.snapshot else 0,
            "data": self.snapshot,
        }

    def daily_report_fact_coverage(self, trade_date):
        return self.coverage

    def query_extreme_conviction_mentions(self, end_date, *, window_days=25, include_a_kill=False):
        return list(self.mentions)


class DailyReportHtmlViewTest(unittest.TestCase):
    def test_builds_view_from_postgres_facts_without_large_json_artifact(self):
        service = FakePostgresDailyReportService(
            snapshot={
                "market_research_snapshot": {
                    "front_page_decision": {
                        "final_action": "0% / 不参与，等待主线承接重新出现",
                        "max_position": "0%",
                        "allow_new_entry": False,
                        "cancel_conditions": ["成交额继续萎缩", "主线扩散不足"],
                    }
                },
                "market_stats": {"up_count": 2600, "down_count": 2100},
                "total_turnover": 1000,
                "mainline_context": {
                    "confirmed_line": "电力",
                    "attack_evidence": ["净流入居前", "高位锚点保持"],
                },
                "data_status": {"两市成交额": True, "大盘涨跌统计": True},
            },
            mentions=[
                {
                    "mention_trade_date": "2026-06-05",
                    "stock_code": "001896",
                    "stock_name": "豫能控股",
                    "planned_window": "09:50-10:10",
                    "review_status": "等待更多事实",
                    "next_action": "只在承接成立时参与",
                    "invalidation": "跌破认错线",
                    "reason": "电力方向前排",
                }
            ],
        )

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertEqual(view["meta"]["trade_date"], "2026-06-05")
        self.assertEqual(view["meta"]["run_mode"], "replay")
        self.assertEqual(view["meta"]["source"], "postgresql://daily-report-facts/2026-06-05")
        self.assertEqual(view["tomorrow_action"]["position_state"], "0%")
        self.assertFalse(view["tomorrow_action"]["can_participate"])
        self.assertEqual(view["market_spine"]["turnover_summary"], "1000")
        self.assertEqual(view["mainline_evidence"]["confirmed_line"], "电力")
        self.assertEqual(view["candidate_actions"][0]["stock_code"], "001896")
        self.assertEqual(view["diagnostics"]["large_json_artifact"], False)
        self.assertTrue(daily_report_view_has_required_facts(view))
        self.assertEqual(missing_required_fact_labels(view), [])

    def test_missing_required_facts_are_reported_without_reading_live_sources(self):
        service = FakePostgresDailyReportService(snapshot={})

        view = build_daily_report_view("2026-06-05", service, run_mode="replay")

        self.assertFalse(daily_report_view_has_required_facts(view))
        self.assertIn("明日动作", missing_required_fact_labels(view))
        self.assertIn("市场结构", missing_required_fact_labels(view))
        self.assertEqual(service.loaded_dates, ["2026-06-05"])
        self.assertEqual(view["diagnostics"]["large_json_artifact"], False)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：失败，错误包含 `No module named 'report.html_report_view'`。

- [ ] **步骤 3：写最小实现**

新建 `scripts/report/html_report_view.py`：

```python
from __future__ import annotations

from typing import Any


__all__ = [
    "build_daily_report_view",
    "daily_report_view_has_required_facts",
    "missing_required_fact_labels",
]


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _first_dict(*values: Any) -> dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _list_text(values: Any) -> list[str]:
    if isinstance(values, list):
        return [_text(value) for value in values if _text(value)]
    if _text(values):
        return [_text(values)]
    return []


def _bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return None
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y", "allow", "allowed"}:
        return True
    if text in {"0", "false", "no", "n", "deny", "denied"}:
        return False
    return None


def _load_postgres_data(target_date: str, db_service: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if db_service is None or not callable(getattr(db_service, "load_daily_report_snapshot", None)):
        return {}, {"source": "", "field_count": 0, "target_field_count": 0}
    loaded = db_service.load_daily_report_snapshot(target_date) or {}
    data = loaded.get("data") if isinstance(loaded.get("data"), dict) else {}
    return data, loaded


def _extract_decision(data: dict[str, Any]) -> dict[str, Any]:
    snapshot = data.get("market_research_snapshot") if isinstance(data.get("market_research_snapshot"), dict) else {}
    return _first_dict(
        snapshot.get("front_page_decision"),
        snapshot.get("tomorrow_decision"),
        data.get("tomorrow_decision"),
        data.get("final_decision"),
    )


def _position_text(decision: dict[str, Any]) -> str:
    for key in ("max_position", "position_state", "position_level", "target_position"):
        value = _text(decision.get(key))
        if value:
            return value
    final_action = _text(decision.get("final_action"))
    if "100%" in final_action:
        return "100%"
    if "50%" in final_action or "B档" in final_action:
        return "50%"
    if "0%" in final_action or "不参与" in final_action:
        return "0%"
    return ""


def _participation_bool(decision: dict[str, Any]) -> bool | None:
    for key in ("allow_new_entry", "can_new_entry", "can_participate"):
        parsed = _bool_or_none(decision.get(key))
        if parsed is not None:
            return parsed
    text = _text(decision.get("final_action"))
    if "不参与" in text or "0%" in text:
        return False
    if "参与" in text or "执行" in text:
        return True
    return None


def _extract_tomorrow_action(data: dict[str, Any]) -> dict[str, Any]:
    decision = _extract_decision(data)
    if not decision:
        return {}
    target = _first_dict(decision.get("primary_target"), decision.get("target"), decision.get("execution_object"))
    return {
        "position_state": _position_text(decision),
        "can_participate": _participation_bool(decision),
        "primary_target": target,
        "participation_window": _text(decision.get("participation_window") or decision.get("buy_window")),
        "action_summary": _text(decision.get("final_action") or decision.get("action_summary")),
        "cancel_conditions": _list_text(decision.get("cancel_conditions") or decision.get("failure_conditions")),
        "risk_boundary": _text(decision.get("risk_boundary") or decision.get("invalidation")),
    }


def _extract_market_spine(data: dict[str, Any]) -> dict[str, Any]:
    market_stats = data.get("market_stats") if isinstance(data.get("market_stats"), dict) else {}
    turnover = data.get("total_turnover")
    market_phase = _text(data.get("market_phase") or data.get("market_trend"))
    return {
        "market_fit": _text(data.get("market_fit") or data.get("market_fit_label")),
        "turnover_summary": _text(turnover),
        "breadth_summary": "上涨{} / 下跌{}".format(
            _text(market_stats.get("up_count")),
            _text(market_stats.get("down_count")),
        ).strip(),
        "market_phase": market_phase,
        "index_structure": _text(data.get("index_structure")),
        "why_it_matters": _text(data.get("market_reason") or data.get("market_summary")),
    }


def _extract_mainline_evidence(data: dict[str, Any]) -> dict[str, Any]:
    context = data.get("mainline_context") if isinstance(data.get("mainline_context"), dict) else {}
    attack_evidence = context.get("attack_evidence")
    return {
        "confirmed_line": _text(context.get("confirmed_line") or context.get("mainline") or data.get("mainline_name")),
        "supporting_lines": _list_text(context.get("supporting_lines")),
        "attack_evidence": _list_text(attack_evidence),
        "turnover_share": _text(context.get("turnover_share")),
        "fund_flow": _text(context.get("fund_flow")),
        "sector_breadth": _text(context.get("sector_breadth")),
        "continuation_conditions": _list_text(context.get("continuation_conditions")),
        "failure_conditions": _list_text(context.get("failure_conditions")),
    }


def _query_candidate_actions(target_date: str, db_service: Any) -> list[dict[str, Any]]:
    reader = getattr(db_service, "query_extreme_conviction_mentions", None)
    if not callable(reader):
        return []
    rows = reader(target_date, window_days=25, include_a_kill=False) or []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "stock_code": _text(row.get("stock_code")),
                "stock_name": _text(row.get("stock_name")),
                "role": _text(row.get("sector_candidate") or row.get("role")),
                "source_reason": _text(row.get("reason")),
                "participation_script": _text(row.get("planned_window") or row.get("buy_window")),
                "entry_timing": _text(row.get("entry_timing")),
                "buy_window": _text(row.get("buy_window") or row.get("planned_window")),
                "risk_reward": _text(row.get("risk_reward")),
                "invalidation": _text(row.get("invalidation")),
                "missed_action": _text(row.get("next_action")),
                "review_status": _text(row.get("review_status")),
            }
        )
    return result


def _data_source_rows(target_date: str, loaded: dict[str, Any], db_service: Any) -> list[dict[str, Any]]:
    rows = [
        {
            "source_label": "PSQL日报事实",
            "source_policy": _text(loaded.get("source")),
            "source_date": target_date,
            "query_date": target_date,
            "trade_date": target_date,
            "status": "success" if int(loaded.get("target_field_count") or loaded.get("field_count") or 0) > 0 else "missing",
            "warning": "",
        }
    ]
    coverage_reader = getattr(db_service, "daily_report_fact_coverage", None)
    coverage = coverage_reader(target_date) if callable(coverage_reader) else {}
    tables = coverage.get("tables") if isinstance(coverage, dict) and isinstance(coverage.get("tables"), dict) else {}
    for table_name, item in tables.items():
        item = item or {}
        rows.append(
            {
                "source_label": _text(table_name),
                "source_policy": "postgresql.{}".format(_text(table_name)),
                "source_date": _text(item.get("max_trade_date")),
                "query_date": target_date,
                "trade_date": target_date,
                "status": "success" if int(item.get("target_count") or 0) > 0 else "missing",
                "warning": "",
            }
        )
    return rows


def _missing_required_facts(view: dict[str, Any]) -> list[str]:
    missing = []
    action = view.get("tomorrow_action") if isinstance(view.get("tomorrow_action"), dict) else {}
    market = view.get("market_spine") if isinstance(view.get("market_spine"), dict) else {}
    sources = view.get("data_sources") if isinstance(view.get("data_sources"), list) else []
    if not action or not _text(action.get("action_summary")):
        missing.append("明日动作")
    if not market or (not _text(market.get("turnover_summary")) and not _text(market.get("breadth_summary"))):
        missing.append("市场结构")
    if not sources or all(_text(item.get("status")) == "missing" for item in sources if isinstance(item, dict)):
        missing.append("数据来源")
    return missing


def build_daily_report_view(target_date: str, db_service: Any, *, run_mode: str = "frozen") -> dict[str, Any]:
    target_date = _text(target_date)
    data, loaded = _load_postgres_data(target_date, db_service)
    candidate_actions = _query_candidate_actions(target_date, db_service)
    view = {
        "meta": {
            "trade_date": target_date,
            "report_title": "{} A股日报".format(target_date),
            "generated_at": "",
            "run_mode": _text(run_mode) or "frozen",
            "source": _text(loaded.get("source")),
            "data_source_summary": "PSQL日报事实",
        },
        "tomorrow_action": _extract_tomorrow_action(data),
        "market_spine": _extract_market_spine(data),
        "mainline_evidence": _extract_mainline_evidence(data),
        "candidate_actions": candidate_actions,
        "participation_reviews": [
            item for item in candidate_actions if _text(item.get("review_status"))
        ],
        "data_sources": _data_source_rows(target_date, loaded, db_service),
        "diagnostics": {
            "missing_required_facts": [],
            "degraded_facts": [],
            "render_warnings": [],
            "html_artifact_path": "",
            "large_json_artifact": False,
        },
    }
    view["diagnostics"]["missing_required_facts"] = _missing_required_facts(view)
    return view


def missing_required_fact_labels(view: dict[str, Any]) -> list[str]:
    diagnostics = view.get("diagnostics") if isinstance(view.get("diagnostics"), dict) else {}
    return list(diagnostics.get("missing_required_facts") or [])


def daily_report_view_has_required_facts(view: dict[str, Any]) -> bool:
    return not missing_required_fact_labels(view)
```

- [ ] **步骤 4：运行测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：`OK`。

- [ ] **步骤 5：提交本任务**

运行：

```bash
git add scripts/report/html_report_view.py tests/test_daily_report_html_view.py
git commit -m "feat(report): add psql html report view"
```

## 任务 2：HTML 渲染器与 Bear 阅读器模板

**文件：**
- 新建：`scripts/report/html_report_renderer.py`
- 新建：`scripts/templates/daily_report_reader.html`
- 测试：`tests/test_daily_report_html_renderer.py`

- [ ] **步骤 1：先写失败测试**

新建 `tests/test_daily_report_html_renderer.py`：

```python
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.html_report_renderer import (
    DailyReportHtmlDataMissingError,
    build_daily_report_html_path,
    render_daily_report_html,
    save_daily_report_html,
)


def _view():
    return {
        "meta": {
            "trade_date": "2026-06-05",
            "report_title": "2026-06-05 A股日报",
            "run_mode": LEDGER_MODE_REPLAY,
            "source": "postgresql://daily-report-facts/2026-06-05",
        },
        "tomorrow_action": {
            "position_state": "0%",
            "can_participate": False,
            "primary_target": {"stock_name": "豫能控股", "stock_code": "001896"},
            "participation_window": "09:50-10:10",
            "action_summary": "不参与 <script>alert(1)</script>",
            "cancel_conditions": ["成交额继续萎缩"],
            "risk_boundary": "跌破认错线",
        },
        "market_spine": {
            "turnover_summary": "1000",
            "breadth_summary": "上涨2600 / 下跌2100",
            "market_phase": "等待承接",
        },
        "mainline_evidence": {
            "confirmed_line": "电力",
            "attack_evidence": ["净流入居前"],
        },
        "candidate_actions": [
            {
                "stock_code": "001896",
                "stock_name": "豫能控股",
                "buy_window": "09:50-10:10",
                "invalidation": "跌破认错线",
                "missed_action": "不追高",
            }
        ],
        "participation_reviews": [],
        "data_sources": [
            {
                "source_label": "PSQL日报事实",
                "source_policy": "postgresql.daily_report_facts",
                "trade_date": "2026-06-05",
                "status": "success",
            }
        ],
        "diagnostics": {"missing_required_facts": [], "large_json_artifact": False},
    }


class DailyReportHtmlRendererTest(unittest.TestCase):
    def test_render_html_escapes_text_and_uses_reader_tokens(self):
        html = render_daily_report_html(_view())

        self.assertIn("2026-06-05 A股日报", html)
        self.assertIn("明日动作", html)
        self.assertIn("--reader-bg: #ffffff", html)
        self.assertIn("--reader-text: #111111", html)
        self.assertIn("--accent-red: #d33a31", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_build_path_uses_replay_suffix_and_html_extension(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            frozen_path = build_daily_report_html_path(
                "2026-06-05",
                root=root,
                run_mode=LEDGER_MODE_FROZEN,
            )
            replay_path = build_daily_report_html_path(
                "2026-06-05",
                root=root,
                run_mode=LEDGER_MODE_REPLAY,
            )

        self.assertEqual(frozen_path.name, "2026-06-05_A股日报_完整版.html")
        self.assertEqual(replay_path.name, "2026-06-05_A股日报_完整版_replay.html")
        self.assertEqual(replay_path.parent.name, "replay")

    def test_save_refuses_missing_required_facts_without_writing_file(self):
        view = _view()
        view["diagnostics"]["missing_required_facts"] = ["明日动作"]

        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            with self.assertRaises(DailyReportHtmlDataMissingError):
                save_daily_report_html(view, root=root)
            self.assertFalse((root / "reports" / "replay").exists())

    def test_save_writes_only_html_not_json(self):
        with TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = save_daily_report_html(_view(), root=root)

            self.assertEqual(path.suffix, ".html")
            self.assertTrue(path.exists())
            self.assertEqual(list(path.parent.glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：失败，错误包含 `No module named 'report.html_report_renderer'`。

- [ ] **步骤 3：写 HTML 模板**

新建 `scripts/templates/daily_report_reader.html`：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title</title>
  <style>
    :root {
      --reader-bg: #ffffff;
      --reader-surface: #f7f7f8;
      --reader-surface-strong: #efeff1;
      --reader-text: #111111;
      --reader-muted: #6b6b70;
      --reader-line: #e5e5e7;
      --accent-red: #d33a31;
      color-scheme: light;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--reader-bg);
      color: var(--reader-text);
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
      line-height: 1.68;
    }
    a { color: var(--accent-red); text-decoration: none; }
    .layout {
      display: grid;
      grid-template-columns: minmax(160px, 220px) minmax(0, 820px);
      gap: 32px;
      width: min(1180px, calc(100% - 48px));
      margin: 0 auto;
      padding: 36px 0 72px;
    }
    .side-nav {
      position: sticky;
      top: 24px;
      align-self: start;
      border-right: 1px solid var(--reader-line);
      padding-right: 18px;
    }
    .side-nav a {
      display: block;
      padding: 7px 0;
      color: var(--reader-muted);
      font-size: 14px;
    }
    .side-nav a:first-child { color: var(--accent-red); font-weight: 700; }
    .reader-main { min-width: 0; }
    .hero {
      border-bottom: 1px solid var(--reader-line);
      padding-bottom: 24px;
      margin-bottom: 24px;
    }
    .date { color: var(--reader-muted); font-size: 14px; }
    h1 {
      margin: 8px 0 0;
      font-size: clamp(30px, 4vw, 46px);
      line-height: 1.16;
      letter-spacing: 0;
    }
    h2 {
      margin: 34px 0 14px;
      font-size: 22px;
      line-height: 1.28;
      letter-spacing: 0;
    }
    .action-panel {
      background: var(--reader-surface);
      border-left: 4px solid var(--accent-red);
      padding: 18px;
      margin: 22px 0;
    }
    .section {
      border-top: 1px solid var(--reader-line);
      padding-top: 6px;
      margin-top: 26px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 22px;
      font-size: 14px;
    }
    th, td {
      border-bottom: 1px solid var(--reader-line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--reader-muted);
      font-weight: 600;
      background: var(--reader-surface);
    }
    .muted { color: var(--reader-muted); }
    .attention { color: var(--accent-red); font-weight: 700; }
    details {
      border: 1px solid var(--reader-line);
      background: var(--reader-surface);
      padding: 10px 12px;
      margin: 10px 0;
    }
    summary { cursor: pointer; color: var(--reader-text); font-weight: 700; }
    @media (max-width: 820px) {
      .layout {
        display: block;
        width: min(100% - 28px, 720px);
        padding-top: 18px;
      }
      .side-nav {
        position: static;
        display: flex;
        gap: 14px;
        overflow-x: auto;
        border-right: 0;
        border-bottom: 1px solid var(--reader-line);
        padding: 0 0 12px;
        margin-bottom: 20px;
      }
      .side-nav a { white-space: nowrap; }
      table { display: block; overflow-x: auto; white-space: nowrap; }
    }
  </style>
</head>
<body>
  <div class="layout">
    <nav class="side-nav" aria-label="日报章节">
      <a href="#tomorrow-action">明日动作</a>
      <a href="#market-spine">市场结构</a>
      <a href="#mainline-evidence">主线证据</a>
      <a href="#candidate-actions">参与对象</a>
      <a href="#reviews">参与预演复盘</a>
      <a href="#data-sources">数据来源</a>
      <a href="#diagnostics">运行诊断</a>
    </nav>
    <main class="reader-main">
      <header class="hero">
        <div class="date">$trade_date</div>
        <h1>$title</h1>
      </header>
      <section id="tomorrow-action" class="action-panel">
        <h2>明日动作</h2>
        $tomorrow_action
      </section>
      <section id="market-spine" class="section">
        <h2>市场结构</h2>
        $market_spine
      </section>
      <section id="mainline-evidence" class="section">
        <h2>主线证据</h2>
        $mainline_evidence
      </section>
      <section id="candidate-actions" class="section">
        <h2>参与对象</h2>
        $candidate_actions
      </section>
      <section id="reviews" class="section">
        <h2>参与预演复盘</h2>
        $participation_reviews
      </section>
      <section id="data-sources" class="section">
        <h2>数据来源</h2>
        $data_sources
      </section>
      <section id="diagnostics" class="section">
        <h2>运行诊断</h2>
        $diagnostics
      </section>
    </main>
  </div>
</body>
</html>
```

- [ ] **步骤 4：写渲染器最小实现**

新建 `scripts/report/html_report_renderer.py`：

```python
from __future__ import annotations

from html import escape
from pathlib import Path
from string import Template
from typing import Any

from daily_report_snapshot_io import LEDGER_MODE_FROZEN, LEDGER_MODE_REPLAY
from report.html_report_view import build_daily_report_view, missing_required_fact_labels


__all__ = [
    "DailyReportHtmlDataMissingError",
    "build_daily_report_html_path",
    "render_daily_report_html",
    "save_daily_report_html",
    "save_daily_report_html_from_postgres",
]


class DailyReportHtmlDataMissingError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_path() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "daily_report_reader.html"


def _html(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _cell(value: Any, *, attention: bool = False) -> str:
    class_attr = ' class="attention"' if attention else ""
    return f"<td{class_attr}>{_html(value)}</td>"


def _table(headers: list[str], rows: list[list[Any]], *, attention_first_row: bool = False) -> str:
    header_html = "".join(f"<th>{_html(header)}</th>" for header in headers)
    if not rows:
        return f"<table><thead><tr>{header_html}</tr></thead><tbody><tr><td colspan=\"{len(headers)}\">暂无数据</td></tr></tbody></table>"
    body_rows = []
    for index, row in enumerate(rows):
        cells = "".join(_cell(value, attention=attention_first_row and index == 0 and cell_index == 1) for cell_index, value in enumerate(row))
        body_rows.append(f"<tr>{cells}</tr>")
    return "<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(header_html, "".join(body_rows))


def _yes_no(value: Any) -> str:
    if value is True:
        return "参与"
    if value is False:
        return "不参与"
    return "待确认"


def _tomorrow_action_html(view: dict[str, Any]) -> str:
    action = view.get("tomorrow_action") if isinstance(view.get("tomorrow_action"), dict) else {}
    target = action.get("primary_target") if isinstance(action.get("primary_target"), dict) else {}
    target_label = "{}({})".format(
        target.get("stock_name") or target.get("name") or "",
        target.get("stock_code") or target.get("code") or "",
    ).strip("()")
    rows = [
        ["明日仓位", action.get("position_state") or "待确认"],
        ["是否参与", _yes_no(action.get("can_participate"))],
        ["参与对象", target_label or "无"],
        ["参与窗口", action.get("participation_window") or "待确认"],
        ["动作摘要", action.get("action_summary") or "待确认"],
        ["取消条件", "；".join(action.get("cancel_conditions") or []) or "待确认"],
        ["风险边界", action.get("risk_boundary") or "待确认"],
    ]
    return _table(["项目", "结论"], rows, attention_first_row=True)


def _market_spine_html(view: dict[str, Any]) -> str:
    market = view.get("market_spine") if isinstance(view.get("market_spine"), dict) else {}
    rows = [
        ["市场适配", market.get("market_fit") or "待确认"],
        ["成交额", market.get("turnover_summary") or "待确认"],
        ["涨跌结构", market.get("breadth_summary") or "待确认"],
        ["市场阶段", market.get("market_phase") or "待确认"],
        ["指数结构", market.get("index_structure") or "待确认"],
        ["含义", market.get("why_it_matters") or "待确认"],
    ]
    return _table(["项目", "内容"], rows)


def _mainline_html(view: dict[str, Any]) -> str:
    item = view.get("mainline_evidence") if isinstance(view.get("mainline_evidence"), dict) else {}
    rows = [
        ["确认主线", item.get("confirmed_line") or "待确认"],
        ["辅助方向", "；".join(item.get("supporting_lines") or []) or "无"],
        ["攻击证据", "；".join(item.get("attack_evidence") or []) or "待确认"],
        ["成交额占比", item.get("turnover_share") or "待确认"],
        ["资金流", item.get("fund_flow") or "待确认"],
        ["扩散", item.get("sector_breadth") or "待确认"],
        ["延续条件", "；".join(item.get("continuation_conditions") or []) or "待确认"],
        ["失败条件", "；".join(item.get("failure_conditions") or []) or "待确认"],
    ]
    return _table(["项目", "证据"], rows)


def _candidate_rows(items: list[dict[str, Any]]) -> list[list[Any]]:
    rows = []
    for item in items or []:
        rows.append(
            [
                "{}({})".format(item.get("stock_name") or "", item.get("stock_code") or "").strip("()"),
                item.get("role") or "待确认",
                item.get("buy_window") or item.get("participation_script") or "待确认",
                item.get("invalidation") or "待确认",
                item.get("missed_action") or "待确认",
            ]
        )
    return rows


def _candidate_actions_html(view: dict[str, Any]) -> str:
    rows = _candidate_rows(view.get("candidate_actions") or [])
    return _table(["标的", "角色", "参与窗口", "认错线", "错过后动作"], rows)


def _reviews_html(view: dict[str, Any]) -> str:
    rows = []
    for item in view.get("participation_reviews") or []:
        rows.append(
            [
                "{}({})".format(item.get("stock_name") or "", item.get("stock_code") or "").strip("()"),
                item.get("review_status") or "等待更多事实",
                item.get("missed_action") or "",
            ]
        )
    if not rows:
        return '<p class="muted">暂无参与预演复盘。</p>'
    return _table(["标的", "复盘状态", "后续动作"], rows)


def _data_sources_html(view: dict[str, Any]) -> str:
    rows = []
    for item in view.get("data_sources") or []:
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
    diagnostics = view.get("diagnostics") if isinstance(view.get("diagnostics"), dict) else {}
    rows = [
        ["缺失关键事实", "；".join(diagnostics.get("missing_required_facts") or []) or "无"],
        ["降级事实", "；".join(diagnostics.get("degraded_facts") or []) or "无"],
        ["HTML路径", diagnostics.get("html_artifact_path") or ""],
        ["每日完整JSON", "未生成" if diagnostics.get("large_json_artifact") is False else "需检查"],
    ]
    return _table(["项目", "结果"], rows)


def build_daily_report_html_path(target_date: str, *, root: str | Path | None = None, run_mode: str = LEDGER_MODE_FROZEN) -> Path:
    root_path = Path(root) if root is not None else _repo_root()
    reports_dir = root_path / "reports"
    suffix = ""
    if run_mode == LEDGER_MODE_REPLAY:
        reports_dir = reports_dir / "replay"
        suffix = "_replay"
    return reports_dir / f"{target_date}_A股日报_完整版{suffix}.html"


def render_daily_report_html(view: dict[str, Any]) -> str:
    meta = view.get("meta") if isinstance(view.get("meta"), dict) else {}
    template = Template(_template_path().read_text(encoding="utf-8"))
    return template.safe_substitute(
        title=_html(meta.get("report_title") or "A股日报"),
        trade_date=_html(meta.get("trade_date") or ""),
        tomorrow_action=_tomorrow_action_html(view),
        market_spine=_market_spine_html(view),
        mainline_evidence=_mainline_html(view),
        candidate_actions=_candidate_actions_html(view),
        participation_reviews=_reviews_html(view),
        data_sources=_data_sources_html(view),
        diagnostics=_diagnostics_html(view),
    )


def save_daily_report_html(view: dict[str, Any], *, root: str | Path | None = None, overwrite_existing: bool = False) -> Path:
    missing = missing_required_fact_labels(view)
    if missing:
        raise DailyReportHtmlDataMissingError("HTML 日报关键数据不完整，停止生成：" + "、".join(missing))
    meta = view.get("meta") if isinstance(view.get("meta"), dict) else {}
    path = build_daily_report_html_path(
        str(meta.get("trade_date") or ""),
        root=root,
        run_mode=str(meta.get("run_mode") or LEDGER_MODE_FROZEN),
    )
    if path.exists() and not overwrite_existing:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    html = render_daily_report_html(view)
    path.write_text(html, encoding="utf-8")
    diagnostics = view.setdefault("diagnostics", {})
    if isinstance(diagnostics, dict):
        diagnostics["html_artifact_path"] = str(path)
    return path


def save_daily_report_html_from_postgres(target_date: str, db_service: Any, *, root: str | Path | None = None, run_mode: str = LEDGER_MODE_FROZEN) -> Path:
    view = build_daily_report_view(target_date, db_service, run_mode=run_mode)
    return save_daily_report_html(view, root=root)
```

- [ ] **步骤 5：运行渲染器测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：`OK`。

- [ ] **步骤 6：提交本任务**

运行：

```bash
git add scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html tests/test_daily_report_html_renderer.py
git commit -m "feat(report): render psql html daily report"
```

## 任务 3：日报入口最小接入

**文件：**
- 修改：`scripts/daily_report_entry_demo.py`
- 测试：`tests/test_daily_report_entry_html_output.py`

- [ ] **步骤 1：先写失败测试**

新建 `tests/test_daily_report_entry_html_output.py`：

```python
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import daily_report_entry_demo


class DailyReportEntryHtmlOutputTest(unittest.TestCase):
    def _valid_data(self):
        return {
            "data_status": {
                "两市成交额": True,
                "中证全指": True,
                "成交额排名": True,
            },
            "total_turnover": 1000,
            "wind_a_alternative": {"price": 5000, "data_source": "tushare.index_daily"},
            "turnover_rank": [{"code": "000001", "data_source": "tushare.daily"}],
            "market_stats": {"up_count": 2600, "down_count": 2100},
            "market_research_snapshot": {
                "front_page_decision": {
                    "final_action": "0% / 不参与",
                    "max_position": "0%",
                    "allow_new_entry": False,
                }
            },
        }

    def test_main_saves_html_after_markdown_when_postgres_facts_are_available(self):
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0% / 不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }
        saved_paths = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "/tmp/summary.md",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths), \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_postgres", return_value=Path("/tmp/2026-06-05_A股日报_完整版.html")) as html_mock:
            daily_report_entry_demo.main()

        html_mock.assert_called_once()
        self.assertEqual(html_mock.call_args.args[0], "2026-06-05")
        self.assertEqual(html_mock.call_args.kwargs["run_mode"], daily_report_entry_demo.LEDGER_MODE_FROZEN)

    def test_html_failure_does_not_prevent_markdown_save(self):
        report_outputs = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "# full\n| 明日执行风格 | 0% / 不参与 |",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "# summary",
        }
        saved_paths = {
            daily_report_entry_demo.REPORT_VARIANT_FULL: "/tmp/full.md",
            daily_report_entry_demo.REPORT_VARIANT_SUMMARY: "/tmp/summary.md",
        }

        with patch.object(sys, "argv", ["daily_report_entry_demo.py", "2026-06-05", "--postgres-only"]), \
             patch.object(daily_report_entry_demo, "load_daily_report_data_from_postgres", return_value=self._valid_data()), \
             patch.object(daily_report_entry_demo, "load_strategy_performance_ledger", return_value={"records": []}), \
             patch.object(daily_report_entry_demo.os.path, "exists", return_value=False), \
             patch.object(daily_report_entry_demo, "build_report_outputs", return_value=report_outputs), \
             patch.object(daily_report_entry_demo, "_build_sh_index_chanlun_html_for_audit", return_value="<h2>明日抉择</h2><table><tr><td>明日最大仓位</td><td>0%</td></tr></table>"), \
             patch.object(daily_report_entry_demo, "save_report_outputs", return_value=saved_paths) as save_markdown_mock, \
             patch.object(daily_report_entry_demo, "save_sh_index_chanlun_html_report", return_value=Path("/tmp/chanlun.html")), \
             patch.object(daily_report_entry_demo, "audit_report_markdown", return_value={"passed": True, "findings": []}), \
             patch.object(daily_report_entry_demo, "import_daily_report_data_to_postgres", return_value={"source": "postgresql://daily-report-facts/2026-06-05", "field_count": 8}), \
             patch.object(daily_report_entry_demo, "_try_save_daily_report_html_from_postgres", return_value=None):
            daily_report_entry_demo.main()

        save_markdown_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **步骤 2：运行测试，确认它按预期失败**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_html_output.py
```

预期：失败，错误包含 `_try_save_daily_report_html_from_postgres` 不存在。

- [ ] **步骤 3：在入口新增 HTML 保存 helper**

修改 `scripts/daily_report_entry_demo.py` 的 import 区域，加入：

```python
from report.html_report_renderer import (
    DailyReportHtmlDataMissingError,
    save_daily_report_html_from_postgres,
)
```

在 `_append_daily_report_duration_log` 前新增：

```python
def _try_save_daily_report_html_from_postgres(target_date, *, run_mode=LEDGER_MODE_FROZEN):
    try:
        service = _postgres_daily_report_service()
        path = save_daily_report_html_from_postgres(
            target_date,
            service,
            root=Path(__file__).resolve().parents[1],
            run_mode=run_mode,
        )
    except (DailyReportHtmlDataMissingError, ReportCriticalDataMissingError, RuntimeError, OSError, UnicodeError) as exc:
        print(f"HTML 日报未生成：{exc}")
        return None
    print(f"HTML 日报已生成: {path}")
    return path
```

- [ ] **步骤 4：在 Markdown 保存后接入 HTML 保存**

在 `saved_report_paths = save_report_outputs(...)` 之后、`save_sh_index_chanlun_html_report(...)` 之前加入：

```python
                _try_save_daily_report_html_from_postgres(
                    target_date,
                    run_mode=run_mode,
                )
```

这一步必须保持：

- Markdown 保存先完成。
- HTML 失败不抛出到主流程。
- 不调用实时源。
- 不写每日完整 JSON。

- [ ] **步骤 5：运行入口测试，确认通过**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 6：提交本任务**

运行：

```bash
git add scripts/daily_report_entry_demo.py tests/test_daily_report_entry_html_output.py
git commit -m "feat(report): save psql html daily report"
```

## 任务 4：联合验证与回归检查

**文件：**
- 修改：无新增代码文件，按实际失败结果只修本计划内文件。

- [ ] **步骤 1：运行 HTML 相关单测**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 2：运行相关既有入口测试**

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_preflight.py
```

预期：`OK`。如果失败，只修本计划新增 HTML 接入导致的问题，不顺手修无关日报逻辑。

- [ ] **步骤 3：检查没有新增每日完整 JSON 产物代码**

运行：

```bash
rg -n "json.dumps|write_text\\(.*json|\\.json" scripts/report/html_report_view.py scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：不出现保存每日完整 JSON 的代码。测试断言中的“没有 JSON 文件”可以出现。

- [ ] **步骤 4：检查禁用用户可见词**

运行：

```bash
rg -n "硬门禁|门禁|gate|hard gate|状态机|状态机词汇" scripts/report/html_report_view.py scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：无输出。若输出来自必须兼容的旧代码字段，改为在实现中用 helper 包装，避免出现在用户可见文本和新测试文案里。

- [ ] **步骤 5：如 PSQL 有目标日期事实，运行一次 PostgreSQL-only 生成**

先选一个 PSQL 中已有事实的日期，例如 `2026-06-05`。如果该日期无事实，不要临时改走实时源。

运行：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --postgres-only
```

预期：

- Markdown 正常保存或按历史保护规则进入 replay。
- 控制台出现 `HTML 日报已生成`，或清楚说明 `HTML 日报未生成：...`。
- 若生成成功，存在 `reports/2026-06-05_A股日报_完整版.html` 或 `reports/replay/2026-06-05_A股日报_完整版_replay.html`。

- [ ] **步骤 6：提交验证修正**

如果任务 4 没有代码修正，不需要提交。

如果修正了本计划内文件，运行：

```bash
git add scripts/report/html_report_view.py scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html scripts/daily_report_entry_demo.py tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
git commit -m "test(report): verify psql html daily report"
```

## 实施约束

- 必须使用 `.generated/venv-py314/bin/python3.14`。
- 不新增每日完整 JSON 文件。
- 不新增每日完整 JSON 表字段。
- 不改写交易判断逻辑。
- 不从实时数据补历史 HTML。
- 不触碰独立前端发布路径。
- 不覆盖用户或其他代理的未提交改动。
- 红色只用于 HTML 阅读器注意力锚点。
- 正文颜色必须接近黑色。

## 自检结果

- 规格中的 PSQL 事实来源：任务 1 覆盖。
- 规格中的 HTML 阅读产物：任务 2 覆盖。
- 规格中的日报入口接入：任务 3 覆盖。
- 规格中的验证与不生成每日完整 JSON：任务 4 覆盖。
- 未使用 `TBD`、`TODO`、`implement later`。
- 后续实现如果发现需要恢复每日完整 JSON，必须停止并回到规格重新讨论。
