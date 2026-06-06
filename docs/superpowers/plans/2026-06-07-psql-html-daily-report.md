# PSQL 驱动 HTML 日报实施计划

> **给代理执行用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务执行。步骤使用复选框（`- [ ]`）格式跟踪。

**目标：** 按已批准规格实现 PSQL 细表驱动的每日 HTML 日报阅读产物，不新增日报大 JSON 附属文件。

**实现思路：** 先建立 `DailyReportView` 查询层，从 `DatabaseService` 读取目标交易日的 PSQL 事实并组装轻量阅读对象。再用独立 HTML 渲染器和 Bear 阅读器式模板输出 HTML。最后在日报入口保存 Markdown 并完成 PSQL 事实同步后生成 HTML，PSQL 不可用或关键事实缺失时只记录原因，不影响 Markdown。

**技术栈：** Python 3.14（固定使用 `.generated/venv-py314/bin/python3.14`）、`unittest`、标准库 `html.escape`、`string.Template`、现有 `DatabaseService` / `daily_report_render` 输出路径规则。

---

## 文件结构

- 新建 `scripts/report/html_report_view.py`
  - 从 PSQL 查询结果组装 `DailyReportView`。
  - 只读传入的 `db_service`，不读实时源，不读历史快照文件。
  - 兼容真实运行链路字段：`front_page_final_gate`、`final_gate`、`position_decision`、`two_layer_decision_payload.front_decision`、`final_target_resolution`、`selected_position_candidate`。

- 新建 `scripts/report/html_report_renderer.py`
  - 把 `DailyReportView` 渲染并保存为 HTML。
  - 对所有用户可见文本做 HTML escape。
  - 输出到 `reports/` 或 `reports/replay/`，只写 `.html`。

- 新建 `scripts/templates/daily_report_reader.html`
  - Bear 阅读器式白、灰、黑、红模板。
  - 红色只用于注意力锚点，正文保持接近黑色。

- 修改 `scripts/daily_report_entry_demo.py`
  - 增加 `_try_save_daily_report_html_from_postgres()`。
  - 在 Markdown 保存、缠论 HTML 保存和 PSQL 事实同步完成后再尝试生成 HTML 日报。

- 新增测试：
  - `tests/test_daily_report_html_view.py`
  - `tests/test_daily_report_html_renderer.py`
  - `tests/test_daily_report_entry_html_output.py`

## 任务 1：PSQL 阅读视图契约

**文件：**
- 新建：`scripts/report/html_report_view.py`
- 测试：`tests/test_daily_report_html_view.py`

- [ ] **步骤 1：先写失败测试**

覆盖以下行为：

- 从 `load_daily_report_snapshot(trade_date)` 读取 PSQL 事实并组装 `meta`、`tomorrow_action`、`market_spine`、`mainline_evidence`、`candidate_actions`、`data_sources`、`diagnostics`。
- `diagnostics.large_json_artifact` 固定为 `False`。
- 缺少明日动作、市场结构或数据来源时返回缺失标签。
- 无显式布尔字段时，`final_action` 为否定参与口径必须得到 `can_participate is False`。
- 真实运行链路字段可以生成明日仓位、参与对象和参与窗口。

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：新增实现前失败，错误来自 `report.html_report_view` 缺失或新行为未实现。

- [ ] **步骤 2：写最小实现**

导出：

```python
build_daily_report_view(target_date, db_service, *, run_mode="frozen")
daily_report_view_has_required_facts(view)
missing_required_fact_labels(view)
```

实现约束：

- 决策字段按“已有事实优先、后写覆盖前写”的方式合并。
- 否定参与口径先于正向参与口径判断。
- 没有明确正向资格时默认 `False`，避免把观察信号误读成可参与。
- 只调用 `load_daily_report_snapshot()`、`daily_report_fact_coverage()`、`query_extreme_conviction_mentions()`。

- [ ] **步骤 3：运行测试，确认通过**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py
```

预期：`OK`。

- [ ] **步骤 4：提交本任务**

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

覆盖以下行为：

- `build_daily_report_html_path("2026-06-05", run_mode="frozen")` 返回 `reports/2026-06-05_A股日报_完整版.html`。
- `run_mode="replay"` 返回 `reports/replay/2026-06-05_A股日报_完整版_replay.html`。
- `render_daily_report_html(view)` 会 escape `<script>` 等文本。
- 模板包含 Bear 阅读器式基础 token：白、灰、黑、网易云红注意力色。
- 缺关键事实时 `save_daily_report_html()` 停止保存。
- 保存 HTML 不产生 `.json` 文件。

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：新增实现前失败，错误来自 `report.html_report_renderer` 缺失。

- [ ] **步骤 2：写最小实现**

导出：

```python
DailyReportHtmlDataMissingError
build_daily_report_html_path(target_date, *, root=None, run_mode="frozen")
render_daily_report_html(view)
save_daily_report_html(view, *, root=None, overwrite_existing=False)
save_daily_report_html_from_postgres(target_date, db_service, *, root=None, run_mode="frozen")
```

实现约束：

- 使用 `string.Template` 读取 `scripts/templates/daily_report_reader.html`。
- 所有进入 HTML 的字段都通过 `html.escape(..., quote=True)`。
- `save_daily_report_html_from_postgres()` 只负责调用 view 层和保存，不直接补实时数据。
- `overwrite_existing=False` 时已存在文件直接返回路径。

- [ ] **步骤 3：运行测试，确认通过**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_renderer.py
```

预期：`OK`。

- [ ] **步骤 4：提交本任务**

```bash
git add scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html tests/test_daily_report_html_renderer.py
git commit -m "feat(report): render psql html daily report"
```

## 任务 3：日报入口最小接入

**文件：**
- 修改：`scripts/daily_report_entry_demo.py`
- 测试：`tests/test_daily_report_entry_html_output.py`

- [ ] **步骤 1：先写失败测试**

覆盖以下行为：

- `--postgres-only` 路径保存 Markdown、保存缠论 HTML、同步 PSQL 事实后再调用 `_try_save_daily_report_html_from_postgres()`。
- 普通路径保存 Markdown、保存快照并同步 PSQL 事实后再调用 HTML 保存。
- HTML 保存失败只返回 `None` 并打印原因，不影响 Markdown 保存。
- 若 `--no-report`，不生成 HTML 日报。

运行：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_html_output.py
```

预期：新增 helper 前失败，错误来自 `_try_save_daily_report_html_from_postgres` 缺失。

- [ ] **步骤 2：写最小实现**

在 import 区加入：

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

入口顺序：

```python
saved_report_paths = save_report_outputs(...)
chanlun_html_path = save_sh_index_chanlun_html_report(...)
...
if data:
    if args.postgres_only:
        result = import_daily_report_data_to_postgres(target_date, data)
    else:
        _save_data_snapshot(data, target_date, mode=run_mode)
        result = import_daily_report_data_to_postgres(target_date, data)
    if not args.no_report:
        _try_save_daily_report_html_from_postgres(target_date, run_mode=run_mode)
```

实现约束：

- Markdown 保存先完成。
- PSQL 事实同步完成后再生成 HTML。
- HTML 失败不抛出到主流程。
- 不新增日报大 JSON。

- [ ] **步骤 3：运行测试，确认通过**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 4：提交本任务**

```bash
git add scripts/daily_report_entry_demo.py tests/test_daily_report_entry_html_output.py
git commit -m "feat(report): save psql html daily report"
```

## 任务 4：联合验证与回归检查

- [ ] **步骤 1：运行 HTML 相关单测**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：`OK`。

- [ ] **步骤 2：运行相关既有入口测试**

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_entry_preflight.py
```

预期：`OK`。如果失败，只修本计划新增 HTML 接入导致的问题。

- [ ] **步骤 3：检查没有新增日报大 JSON 产物代码**

```bash
rg -n "json.dumps|write_text\\(.*json|\\.json" scripts/report/html_report_view.py scripts/report/html_report_renderer.py scripts/templates/daily_report_reader.html tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

预期：不出现保存日报大 JSON 的代码。测试断言中的“没有 JSON 文件”可以出现。

- [ ] **步骤 4：检查用户可见文字遵守术语契约**

```bash
.generated/venv-py314/bin/python3.14 - <<'PY'
from pathlib import Path

terms = []
text = Path("AGENTS.md").read_text(encoding="utf-8")
start = text.find("明确禁用以下说法：")
end = text.find("需要表达检查", start)
if start >= 0 and end > start:
    section = text[start:end]
    terms = [part for index, part in enumerate(section.split("`")) if index % 2 == 1]

paths = [
    Path("scripts/templates/daily_report_reader.html"),
]
violations = []
for path in paths:
    content = path.read_text(encoding="utf-8")
    for term in terms:
        if term and term in content:
            violations.append(f"{path}: contains old report wording")
if violations:
    raise SystemExit("\\n".join(violations))
print("OK")
PY
```

预期：`OK`。这一步只检查用户可见模板，不扫描内部兼容字段名。渲染后的 HTML 文案由 `tests/test_daily_report_html_renderer.py` 覆盖。

- [ ] **步骤 5：如 PSQL 有目标日期事实，运行一次 PostgreSQL-only 生成**

先选一个 PSQL 中已有事实的日期，例如 `2026-06-05`。如果该日期无事实，不要临时改走实时源。

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --postgres-only
```

预期：

- Markdown 正常保存或按历史保护规则进入 replay。
- 控制台出现 `HTML 日报已生成`，或清楚说明 `HTML 日报未生成：...`。
- 若生成成功，存在 `reports/2026-06-05_A股日报_完整版.html` 或 `reports/replay/2026-06-05_A股日报_完整版_replay.html`。

- [ ] **步骤 6：运行一次 replay 入口验证**

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-06-05 --replay
```

预期：

- 不切到实时源补历史 HTML。
- 若目标日期 PSQL 事实缺失，HTML 给出缺失原因，Markdown replay 仍按既有路径执行。

## 实施约束

- 必须使用 `.generated/venv-py314/bin/python3.14`。
- 不新增日报大 JSON 文件。
- 不新增日报大 JSON 表字段。
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
- 规格中的验证与不生成日报大 JSON：任务 4 覆盖。
- 后续实现如果发现需要恢复日报大 JSON，必须停止并回到规格重新讨论。
