# 日报 CLI 进度与运行台账设计

## 背景

当前日报系统已经有 Python 运行时、hook pipeline、trace、run log、module log、replay 和大量测试，但用户在 Codex 下运行日报时仍然像面对黑盒：akshare 遇到反爬或慢请求时不知道卡在哪一步，DeepSeek 超时异常时没有清晰提示，运行完成后也缺少一份可直接复盘的“今日运行台账”。

本设计采用 Newton iteration 的 1.0 思路：不先改成 Python 常驻服务，也不先上 Go 后端；先把一次性 CLI 运行变成可观察、可复盘、可继续迭代的样本。

## 1.0 判断

第一版应做“日报 CLI Runner + 实时进度条 + 事件日志 + 运行台账”。

不做服务化的原因：

- 当前核心痛点是运行过程不可见，而不是缺少远程访问、多用户权限或网页后台。
- 现有 Python 代码和测试沉淀适合作为日报运行内核，重写 Go 后端会先消耗在工程壳上。
- 结构化台账一旦稳定，后续 FastAPI 或 Go 后端可以直接消费这些产物。

## 目标

- 运行中持续显示 hook 总进度、当前 hook 和总耗时。
- 关键事件一行一行及时输出，不被动态进度条吞掉。
- akshare 和 DeepSeek 这两个高风险外部调用先接入统一观测。
- 运行后生成可读的 `overview.md` 和可编辑的 `review_queue.md`。
- 所有运行事件同时写入结构化 JSON，支持后续服务化或回放分析。

## 非目标

- 不引入常驻 Python 服务。
- 不引入 Go 后端。
- 不一次性重构所有数据源调用。
- 不追求完整 Web dashboard。
- 不把人工交易判断自动化；只把待确认项显性化。

## CLI 体验

TTY 支持动态刷新时，底部或当前状态行显示：

```text
[████████████░░░░░░░░] 6/10 hooks  current=knowledge.llm_wiki  elapsed=02:14
```

关键事件仍然作为独立日志行保留：

```text
[10:21:08] input.hot_rank      akshare stock_zh_a_hist attempt=1 timeout=15s
[10:21:23] input.hot_rank      WARN akshare timeout after 15s, retry=2/2
[10:21:39] input.hot_rank      WARN akshare failed, fallback=tencent
[10:21:42] input.hot_rank      OK fallback=tencent rows=30 duration=3.1s
[10:22:01] calendar_events.llm deepseek request model=deepseek-v4-flash timeout=30s
[10:22:31] calendar_events.llm WARN deepseek timeout, fallback=minimal_analysis
```

如果 Codex 捕获环境不稳定支持同一行刷新，则退化成周期性进度行：

```text
[progress] 6/10 hooks current=knowledge.llm_wiki elapsed=02:14
```

## 架构

新增一个轻量运行观测层，挂在现有 pipeline 和高风险 provider 调用外侧。

```text
daily_report_entry_demo.py
  -> run_with_log_capture
  -> pipeline_runner.run_pipeline
       -> RunProgressReporter
       -> TraceRuntime
       -> module_logs
       -> provider event wrappers
  -> run ledger writer
```

### RunProgressReporter

职责：

- 记录总 hook 数、当前 hook、已完成 hook、开始时间、总耗时。
- 在 hook 开始、成功、失败时刷新进度。
- 在 provider 事件发生时输出一行日志。
- 根据环境选择动态刷新或普通日志 fallback。

事件入口：

- `hook_start`
- `hook_success`
- `hook_error`
- `hook_progress`
- `provider_call_start`
- `provider_call_success`
- `provider_call_timeout`
- `provider_call_retry`
- `provider_call_fallback`
- `provider_call_error`

### Provider 事件

第一版只强制覆盖：

- akshare 相关高风险访问。
- DeepSeek / LLM 调用。

事件字段：

| 字段 | 含义 |
| --- | --- |
| `event_type` | provider_call_start/success/timeout/retry/fallback/error |
| `hook_name` | 当前 hook 或调用方模块 |
| `provider` | akshare/deepseek/tencent/minimal 等 |
| `operation` | stock_zh_a_hist、analyze_events_batch 等 |
| `attempt` | 当前尝试次数 |
| `max_attempts` | 最大尝试次数 |
| `timeout_sec` | 本次调用超时阈值 |
| `duration_ms` | 本次调用耗时 |
| `fallback_provider` | 降级目标 |
| `rows` | 返回数据行数，若适用 |
| `error_type` | TimeoutError、HTTPError 等 |
| `error_message` | 可读错误摘要 |

### 运行台账

每次运行生成：

```text
reports/runs/YYYY-MM-DD/
├── overview.md
├── run.json
├── module_logs.json
├── provider_events.json
├── review_queue.md
└── artifacts.json
```

`overview.md` 面向用户第一眼阅读：

- 运行状态：success、success_with_warnings、error。
- 总耗时。
- Hook 完成数。
- fallback 数。
- error 数。
- 今日需要人工确认的事项。

`review_queue.md` 面向后续人工校准：

```md
- [ ] input.hot_rank fallback 后结果是否可接受？
  - 原因：akshare timeout，已 fallback 到 tencent
  - 人工判断：
  - 后续优化：

- [ ] calendar_events.llm fallback 后产业链归类是否可接受？
  - 原因：DeepSeek timeout，使用 minimal_analysis
  - 人工判断：
  - 后续优化：
```

## 数据流

1. CLI 启动时创建 run id、run root 和 reporter。
2. pipeline_runner 根据 hook 列表初始化总进度。
3. 每个 hook 开始时输出进度并写入事件。
4. 每个 hook 内部遇到 akshare 或 DeepSeek 调用时，通过 provider wrapper 发事件。
5. hook 结束时写入 module log、trace event，并推进 hook 进度。
6. 运行结束时汇总 trace、module logs、provider events、artifacts。
7. 写出 `overview.md` 和 `review_queue.md`。

## 错误处理

- hook error：立即显示失败 hook、错误摘要、已耗时，并保留现有异常传播行为。
- provider timeout：显示 timeout、attempt、fallback 或失败原因。
- provider fallback：不静默降级，必须进入 provider event、overview 和 review queue。
- Codex 非 TTY：不依赖控制字符，保证至少周期性打印可读进度行。
- 运行被中断：保留已写事件，并在 run.json 中标记 `interrupted`。

## Newton 校准字段

| 现象 | 字段化记录 |
| --- | --- |
| akshare 很慢或反爬 | `provider=akshare`、`operation`、`timeout_sec`、`duration_ms`、`attempt`、`fallback_provider` |
| DeepSeek 超时 | `provider=deepseek`、`model`、`timeout_sec`、`retry_count`、`degraded_result` |
| Codex 下无提示 | `hook_progress`、`current_hook`、`elapsed`、实时日志行 |
| 跑完不知道怎么优化 | `review_queue.md` 的原因、影响、人工判断、后续优化 |

## 验收标准

- 运行日报时能看到类似：

```text
[████████████░░░░░░░░] 6/10 hooks  current=knowledge.llm_wiki  elapsed=02:14
```

- akshare timeout 或 fallback 时，CLI 输出一行明确事件。
- DeepSeek timeout 或 fallback 时，CLI 输出一行明确事件。
- 非 TTY/Codex 捕获环境下仍能看到 `[progress]` 进度行。
- 运行结束后生成 `reports/runs/YYYY-MM-DD/overview.md`。
- 有 fallback 或 error 时，`review_queue.md` 至少包含一条待人工确认项。
- JSON 产物可以被单元测试读取并断言关键字段。

## 测试策略

- `RunProgressReporter` 单元测试：hook 进度、elapsed、动态/非动态输出 fallback。
- `provider_events` 单元测试：timeout、retry、fallback、success 的字段完整性。
- `overview.md` 渲染测试：success_with_warnings、error、fallback review item。
- pipeline 集成测试：两个假 hook，一个成功一个 fallback，断言进度、module log 和 provider events。
- 保留现有 `run_log_runtime` 测试，确保 stdout/stderr 仍同步写入 run log。

## 后续迭代触发条件

- 如果 akshare timeout 仍频繁发生，再做 provider 级缓存或数据源优先级调整。
- 如果 DeepSeek timeout 仍影响报告质量，再拆分 LLM 调用、增加更短 prompt 或明确离线 fallback。
- 如果用户开始需要历史运行筛选或图形界面，再基于结构化台账做本地 Python dashboard。
- 如果需要服务器部署，再考虑 Go 后端调度 Python 内核。
