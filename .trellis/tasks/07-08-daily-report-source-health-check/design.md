# Design: 日报生成前数据源健康检查

## Scope And Boundaries

本设计只新增“生成前检查”能力，并把检查结论接入完整日报入口。它不改变日报里的判断链路、候选池、仓位、执行性质或 replay 覆盖策略。

第一版以最小闭环为目标：

- 一个健康检查 CLI。
- 一个结构化 JSON 输出。
- 一个 Bear 风格 HTML 检查表。
- 一个入口接入点：关键项失败时停止完整生成并打印检查表路径。
- 一组单测覆盖凭证、脱敏、失败、超时和 HTML 表格。

## Contracts / Data Flow

### 运行流程

```text
用户运行日报生成
  -> 解析目标日期
  -> 执行 source health 检查
  -> 写入 JSON + HTML
  -> 若关键项失败：停止完整生成，打印失败摘要和 HTML 路径
  -> 若检查通过：进入现有 get_daily_data / build_report_outputs / 保存链路
```

### JSON 契约

```python
{
    "schema_version": "daily_report_source_health.v1",
    "target_date": "YYYY-MM-DD",
    "generated_at": "YYYY-MM-DD HH:MM:SS",
    "duration_ms": 0,
    "overall_result": "ready | wait_data | stop_generation",
    "blocking_failures": ["str"],
    "warnings": ["str"],
    "checks": [
        {
            "id": "tushare.runtime",
            "group": "基础市场事实",
            "task": "Tushare B 通道",
            "provider": "tushare.b.index_basic",
            "credential_keys": ["TUSHARE_TOKEN", "TUSHARE_HTTP_URL"],
            "credential_status": "ok | missing | suspected_expired | not_required | not_checked",
            "connectivity_status": "ok | failed | timeout | not_checked",
            "target_date_status": "covered | missing | not_applicable | not_checked",
            "row_count": 0,
            "duration_ms": 0,
            "required_for_generation": True,
            "result": "pass | fail | warning | skipped",
            "advice": "str",
            "safe_error": "str"
        }
    ],
    "artifacts": {
        "json_path": "logs/source_health/<date>_source_health.json",
        "html_path": "logs/source_health/<date>_source_health.html"
    }
}
```

### 检查行分类

| 分组 | 第一版检查项 | 生成影响 |
|---|---|---|
| 基础市场事实 | Tushare token/proxy、目标日期基础行情、指数、成交额 | 失败则停止生成 |
| 持久化事实 | PostgreSQL URL、目标日期事实覆盖、PostgreSQL-only 读取条件 | 依运行模式决定是否停止 |
| 当日热度与叙事 | 雪球 A 股 24 小时热榜、雪球 AI 理由 | 若作为关键判断因子失败则停止生成 |
| 加工模型 | QuickTiny 异动检测、板块四象限 | 按数据源契约判定关键或增强 |
| 回补和备用 | iwencai、Xuangubao、Investor QA endpoint | 关键字段失败则停止；可选补充缺失则 warning |
| LLM | DeepSeek / 远程日历分析 | 仅在相关功能启用时检查 |

### HTML 表格

HTML 只消费 JSON，不访问外部源。建议列：

| 列 | 含义 |
|---|---|
| 数据源任务 | 用户能识别的任务名 |
| 用途 | 基础事实 / 决策事实 / 展示增强 |
| 凭证 | `✓` / `×` / `-` |
| 接口 | `✓` / `×` / `-` |
| 目标日期 | `✓` / `×` / `-` |
| 记录数 | 数字或 `-` |
| 耗时 | 毫秒或秒 |
| 结论 | 可生成 / 等待数据 / 停止生成 / 可跳过 |
| 建议 | 修复动作 |

视觉规则：

- `✓` 表示满足。
- `×` 表示不满足。
- `-` 表示不适用或未检查。
- 颜色只做辅助，文本必须完整。
- 表格样式靠近现有 Bear HTML：窄边框、清晰标题、紧凑行距。

## Compatibility / Migration

- 默认保留现有 `daily_report_entry_demo.py` 命令形态。
- 新增 `--source-health-only` 可只生成检查表，不进入完整日报生成。
- 第一版入口接入可先放在 `get_daily_data()` 前；后续若改成 pipeline hook，需要保持 JSON/HTML 契约不变。
- 若用户运行 replay，健康检查默认只检查本地快照和 replay 所需事实，不触发当前实时数据源。

## Tradeoffs

- 健康检查不是完整采集。它只判断关键路径是否值得进入完整生成，因此不能保证完整生成 100% 成功。
- 第一版优先让失败早暴露，而不是一次性优化所有慢源。
- 对凭证过期的判断以探测结果为准：缺失可以直接判断，过期通常通过 401/403、空返回、登录态错误或 provider 明确错误推断。

## Rollback / Roll-forward

- 回滚：移除入口接入点后，独立健康检查 CLI 和 HTML 仍可保留，不影响日报生成。
- 前进：后续可把慢源耗时历史写入 PostgreSQL 或运行日志，用于生成源稳定性趋势；这不属于第一版。
