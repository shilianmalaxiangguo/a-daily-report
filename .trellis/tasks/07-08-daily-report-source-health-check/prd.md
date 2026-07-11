# 日报生成前数据源健康检查

状态：✅ 已完成

## Goal

为日报生成链路增加生成前数据源健康检查和 Bear 风格 HTML 检查表，让日报在正式采集和渲染前先确认关键数据源、凭证、目标日期覆盖和耗时预算是否满足生成条件，减少“10 分钟到 2 小时全看运气”的不稳定运行。

## User Story

- **角色**：日报维护者
- **场景**：准备生成当日或指定日期日报前
- **目标**：先看到每个关键数据源的可用性、凭证情况、目标日期覆盖、耗时和处理建议
- **成功标准**：如果关键数据源不可用，系统在完整生成前停止，并输出可打开的 HTML 检查表；如果满足生成条件，用户能看到每个数据源打勾后再进入生成链路。

### 用户旅程

1. 用户运行生成前健康检查命令 → 系统输出 JSON 和 Bear 风格 HTML 检查表。
2. 用户查看检查表 → 每个数据源任务以 `✓` / `×` / `-` 显示凭证、接口、目标日期、记录数和耗时。
3. 若关键检查失败 → 系统停止完整生成，并给出修复建议和检查表路径。
4. 若检查通过 → 用户运行完整日报生成，入口复用同一检查结果或重新执行轻量检查。

## What I Already Know

- 入口已有 Tushare 跑前检查：`daily_report_entry_demo._run_tushare_provider_precheck()`。
- 结果级检查已有 `build_report_preflight()`，但它发生在采集和报告构建之后，无法提前控制慢源和凭证失效。
- 请求诊断已有 `build_request_diagnostics()`，可统计 request 日志、失败、降级和回退。
- 日报数据源契约要求登记过的判断因子失败、未采集或载荷为空时停止生成。
- 当前关键凭证和连接项包括：`TUSHARE_TOKEN`、`TUSHARE_HTTP_URL`、`XUEQIU_COOKIE`、`XUEQIU_COOKIE_CAPTURE_DIR`、`QUICKTINY_EXCHANGE_MONITOR_TOKEN`、`QUICKTINY_TOKEN`、`IWENCAI_API_KEY`、`IWENCAI_BASE_URL`、`XUANGUBAO_IVANKA_TOKEN`、`INVESTOR_QA_ENDPOINT_URL`、`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`A_DAILY_REPORT_DATABASE_URL`、`DATABASE_URL`。
- 凭证值不得进入日志、JSON、HTML 或异常信息，只允许显示“已配置 / 未配置 / 疑似失效 / 未检查”。

## Requirements

- [x] R1: 新增生成前数据源健康检查命令，支持传入目标日期，输出机器可读 JSON。
- [x] R2: 健康检查必须覆盖关键凭证、连接、接口可达性、目标日期覆盖、最小记录数、耗时和处理建议。
- [x] R3: 新增 Bear 风格 HTML 检查表，表格按数据源任务逐行展示，并用 `✓` / `×` / `-` 表示检查结果。
- [x] R4: 健康检查必须把数据源分为“影响生成条件”和“只影响展示增强”两类，关键项失败时给出停止生成结论。
- [x] R5: 日报入口接入健康检查：完整生成前先执行或读取健康检查结果，关键项失败时不进入重采集和渲染。
- [x] R6: 日志和 HTML 必须做敏感信息脱敏，不输出 token、cookie、数据库连接串、API key 原文。
- [x] R7: 每个检查项必须有独立超时，整体健康检查应在固定预算内结束。
- [x] R8: 检查结果必须保存到稳定路径，方便 Bear 打开和事后复盘。

## Non-functional Requirements

### 性能

- 健康检查目标耗时不超过 90 秒。
- 单个外部源检查必须有独立超时，默认不超过 15 秒；Tushare 可沿用已有 60 秒跑前检查，但后续应收敛到更细粒度探测。
- HTML 渲染只读取健康检查结果，不再访问外部源。

### 安全

- 不记录任何凭证原文。
- 对异常信息复用现有脱敏规则，并扩展到 `XUEQIU_COOKIE`、`IWENCAI_API_KEY`、`XUANGUBAO_IVANKA_TOKEN`、数据库 URL 等字段。
- HTML 中只显示凭证来源和健康结论，不显示值。

### 兼容性

- 所有命令使用 `.generated/venv-py314/bin/python3.14`。
- 不改变现有 replay 策略，不覆盖正式历史日报。
- 第一版不改现有日报决策生成逻辑。

### 可访问性

- HTML 表格保留文本状态，不只依赖颜色。
- 每行提供明确“处理建议”列，便于复制到 Bear 后阅读。

## Acceptance Criteria

- [x] AC-R1-1: 给定目标日期，当运行健康检查命令时，生成 `logs/source_health/<date>_source_health.json`。
- [x] AC-R1-2: JSON 至少包含 `target_date`、`overall_result`、`generated_at`、`duration_ms`、`checks[]`、`blocking_failures[]`、`warnings[]`。
- [x] AC-R2-1: 每个 `checks[]` 行包含数据源名、任务名、凭证状态、接口状态、目标日期状态、记录数、耗时、生成影响和处理建议。
- [x] AC-R2-2: 若雪球 cookie 缺失、失效或返回空，而该源仍被列为关键判断因子，检查结论为停止生成。
- [x] AC-R2-3: 若 Tushare token 或 proxy 不可用，检查结论为停止生成。
- [x] AC-R2-4: 若可选展示源缺失，检查结论保留为可生成，但 warnings 写清缺失影响。
- [x] AC-R3-1: 给定同一 JSON，当运行 HTML 渲染时，生成 `logs/source_health/<date>_source_health.html`。
- [x] AC-R3-2: HTML 表格每个任务行显示 `✓` / `×` / `-`，并且不需要打开完整日报即可判断哪个源有问题。
- [x] AC-R4-1: 关键项失败时，完整日报入口在重采集前停止，并打印 HTML 路径。
- [x] AC-R5-1: 健康检查通过时，完整日报生成继续沿用现有数据采集、报告构建和一致性检查。
- [x] AC-R6-1: 单测覆盖 token、cookie、数据库 URL、Bearer token 的脱敏，输出中不得出现原始敏感值。
- [x] AC-R7-1: 单测覆盖单源超时，结果行显示超时和处理建议，整体命令仍能结束。
- [x] AC-R8-1: 最新一次检查写入 `logs/source_health/latest_source_health.json` 和 `logs/source_health/latest_source_health.html`。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已补齐并通过 review。
- [x] 必要研究记录保存在 `research/`。
- [x] 新增或更新单测通过。
- [x] 使用 Python 3.14 跑最小验证命令。
- [x] PRD 状态改为 `✅ 已完成`；当前尚未提交 commit。

## Out Of Scope

- 不重构完整日报主链路。
- 不替换现有数据源优先级。
- 不改明日标的、仓位、执行性质的生成逻辑。
- 不覆盖正式历史日报。
- 不把可选展示增强源失败伪装成关键事实失败。
- 不实现长期运行监控、告警推送或远程仪表盘。

## Non-goals

- 不解决所有慢源问题，只先让慢源、凭证失效和目标日期缺口可见、可停止、可复盘。
- 不在 HTML 中展示任何真实 token、cookie 或数据库连接串。
- 不用当前实时数据回补历史日期。

## Technical Notes

### 参考来源

- `wiki/运行契约/日报数据源契约.md`
- `openspec/specs/architecture/error-handling.md`
- `openspec/specs/architecture/observability.md`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/tasks/07-08-daily-report-source-health-check/research/source-health-evidence.md`

### 影响区域

- 新增健康检查运行时模块和 CLI。
- 新增 Bear 风格 HTML 渲染模板或复用现有 HTML 样式。
- 日报入口在完整生成前调用健康检查。
- 请求诊断和运行日志脱敏规则补充。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_source_health`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_entry_preflight`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_source_health.py 2026-07-08`
- `.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py 2026-07-08 --no-report`

## 落地 commit

实现与验证已完成，当前尚未提交 commit。
