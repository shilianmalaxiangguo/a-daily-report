# 日报事实数据库与 JSON 导出管道设计

日期：2026-05-12

## 结论

日报数据层应该一步到位按 `Postgres` 设计。`SQLite` 可以继续作为本地过渡索引、测试替身或离线小样本缓存，但不要再把它作为未来事实库；Cloudflare D1 也只适合轻量索引、公开缓存或边缘读模型，不适合作为 A 股全市场历史事实库。

核心方向：

```text
Tushare / existing providers
  -> MarketDataService
  -> DatabaseService / Repository
  -> fact tables + derived tables
  -> JsonExportService
  -> report runtime / snap-ui / Go or Cloudflare API payloads
```

`JSON` 从现在开始要降级成“导出产物、回放材料、发布 payload”，不再是事实源。新需求不能再靠连续读取多个 `snapshots/*.json` 拼数据；要先落库，再由查询服务或导出服务生成需要的 JSON。

## In Scope

- 设计 Tushare 默认、旧数据源 fallback 的查询 service 边界。
- 设计数据库 service 边界，让外部不感知底层是 Postgres、SQLite 测试替身还是未来其他存储。
- 设计第一批 Postgres fact/derived 表，支撑 `近30天成交额前50占两市成交额比例`、`近25日/周主线定义`、`主线与成交额占比`。
- 设计从 DB 生成 JSON 的受控出口，替代散落的 `json.dump/write_text`。
- 说明 Cloudflare/Go 后端应该如何读取这套数据。

## Out of Scope

- 不在本 spec 里把全仓库所有 JSON 写入点一次性迁移完。
- 不删除现有 AkShare、BaoStock、QuickTiny、腾讯/同花顺等 provider。
- 不重写现有日报生成链路、Chanlun、中枢、report onion 或 snap-ui。
- 不在第一期实现完整支付、权限、队列和 SaaS 管理台。

## Non-goals

- 不追求 Tushare 100% 替代所有现有数据源。
- 不把数据库表设计成一次覆盖所有未来金融数据的超大模型。
- 不让 Cloudflare Worker 直接跑 Tushare、pandas 或日报生成逻辑。
- 不通过正则解析 markdown 或 JSON 快照来反推事实数据。

## 当前事实

仓库当前已有两类过渡能力：

- `scripts/market_data/tushare_client.py` 统一保存了 Tushare 初始化方式，包含自定义网关赋值 `pro._DataApi__http_url = ...`，这是后续所有 Tushare provider 必须复用的入口。
- `scripts/storage/daily_snapshot_sqlite.py` 已经证明“从 JSON 快照回填索引”能解决短期查询问题，但它的事实方向是反的：它仍然依赖快照文件先存在。

当前散落 JSON 写入点包括但不限于：

- `scripts/daily_report_snapshot_io.py` 写 `snapshots/` 和 `snapshots/replay/`。
- `scripts/report_onion/publisher.py` 写公开版/私有版日报 JSON。
- `scripts/market_data/minute_price_runtime.py` 写分钟缓存。
- `scripts/report/strategy_tracking_store.py` 写策略账本和 factor snapshot。
- `scripts/research/tracking_memory_runtime.py` 写跟踪记忆状态。
- `scripts/orchestrator/run_log_runtime.py` 写运行日志 JSON。

这些文件在回放、审计、UI 展示上仍然有价值，但新链路不能再把它们当作跨日查询的主索引。

## Tushare 能力判断

Tushare 应该成为默认事实 provider，原因是它提供稳定 SDK/API、DataFrame schema 明确，并且可以按交易日一次拉全市场数据，避免 AkShare 反爬、网页结构变化和隐式失败带来的不确定性。

已确认适合进入默认层的接口：

| 需求 | Tushare 接口 | 用法 |
|---|---|---|
| 股票基础信息 | `stock_basic` | 股票代码、名称、上市状态、行业基础字段 |
| 个股日线 | `daily` / `pro_bar` | 日线 OHLCV，`pro_bar` 用于复权行情 |
| 指数基础信息 | `index_basic` | 指数列表、指数代码 |
| 指数日线 | `index_daily` / `pro_bar` | 上证、深证、创业板等指数行情 |
| 每日指标 | `daily_basic` | 换手率、市值、市盈率等 |
| 个股资金流 | `moneyflow` | 大单/小单/主力资金方向 |
| 涨跌停/炸板 | `limit_list_d` | 涨停、跌停、炸板、封单等打板数据 |
| 成交额排行 | `daily(trade_date=...)` | 用 `amount` 排序得到全市场前 N，`amount` 单位按 Tushare 文档为千元 |

Tushare 不是完美替代：

- 盘中实时、分钟级体验、热榜、顽主杯、部分同花顺/东方财富榜单，仍可能需要现有 provider 或专用接口。
- 板块/主线语义不是单个行情接口能直接给出的，仍需要当前日报里的主线识别逻辑、行业归并白名单和资金解释层。
- Tushare 的权限、积分、频率和第三方网关稳定性仍要进入 provider health，不允许静默失败后看起来像成功。

因此结论是：Tushare 做默认事实源，旧 provider 做 fallback/specialized adapter。

## 方案比较

### 方案 A：继续 JSON + SQLite 索引

优点：

- 改动小。
- 本地运行简单。
- 现有 replay 基本不受影响。

缺点：

- 事实源仍然是 JSON，跨日查询要先找文件再归并。
- 很难做 30 天、90 天、全市场成交额排行、主线占比这类窗口查询。
- SQLite 索引会慢慢变成第二套事实，和 JSON 漂移。

判断：只适合作为过渡补丁，不适合作为目标架构。

### 方案 B：先 SQLite，后面再迁 Postgres

优点：

- 本地部署轻，测试方便。
- 可以先把 repository/service 边界立起来。

缺点：

- 很快会遇到并发、窗口查询、物化视图、SaaS 后端、Cloudflare 接入问题。
- SQLite 到 Postgres 的 SQL、迁移、类型、时间字段、JSON 字段都会产生二次迁移成本。
- 用户当前明确要的是跨日、全市场、可演进查询，不是单机小工具。

判断：可以作为测试替身，但不作为产品事实库。

### 方案 C：Postgres-first，SQLite 只做测试/本地 fallback

优点：

- 直接匹配跨日窗口、聚合、排名、物化视图、JSONB payload 和后端 API。
- 适合 SaaS 权限、任务、日志、provider health、artifact 索引一起演进。
- Cloudflare Workers 可以通过 Hyperdrive 查询 Postgres，Go 后端也天然适配。

缺点：

- 本地需要 Postgres 或 Docker。
- 第一阶段要写 migration、repository 和少量运维脚本。

推荐选择：方案 C。

## 服务边界

### MarketDataService

职责：

- 对外提供稳定查询方法，不暴露 Tushare/AkShare/BaoStock/腾讯等实现细节。
- 默认走 Tushare，失败或字段不足时走 fallback adapter。
- 返回统一 domain record，不把 pandas DataFrame 泄露到业务层。
- 每次请求记录 provider、参数、耗时、行数、错误、是否 fallback。

建议接口：

```text
get_stock_daily_quotes(trade_date | start_date/end_date, ts_codes?)
get_index_daily_quotes(index_codes, start_date, end_date)
get_stock_daily_basic(trade_date)
get_stock_moneyflow(trade_date)
get_limit_list(trade_date)
get_market_turnover_rank(trade_date, limit)
get_sector_turnover_snapshot(trade_date, sector_scope)
```

实现层：

```text
market_data/
  tushare_client.py          # 只负责初始化 pro，保留自定义网关必填行
  providers/
    tushare_provider.py
    legacy_quicktiny_provider.py
    legacy_baostock_provider.py
    tencent_sector_provider.py
  services/
    market_data_service.py
```

### DatabaseService / Repository

职责：

- 统一 upsert、query、transaction、migration。
- 外部只调用 repository 方法，不直接写 SQL 文件或 JSON 文件。
- 第一阶段主实现是 Postgres，测试可以用 SQLite adapter 或临时 Postgres。

建议接口：

```text
upsert_stock_daily_quotes(rows, source_run_id)
upsert_index_daily_quotes(rows, source_run_id)
upsert_stock_daily_basic(rows, source_run_id)
upsert_moneyflow_daily(rows, source_run_id)
upsert_limit_list_daily(rows, source_run_id)
save_mainline_daily(record, source_run_id)
save_sector_turnover_daily(record, source_run_id)
save_report_artifact(record)

query_top_turnover_share(trade_date, limit=50)
query_top_turnover_share_series(end_date, window_days=30, limit=50)
query_mainline_history(end_date, lookback_days=25)
query_mainline_turnover_series(end_date, lookback_days=25)
```

### JsonExportService

职责：

- 唯一负责从 DB 生成 JSON payload。
- 对外产出 `snapshot JSON`、`report onion JSON`、`snap-ui API JSON`、`Cloudflare/Go API payload`。
- 所有导出都有 `schema_version`、`source_run_id`、`query_window`、`generated_at`。
- 不从 markdown 或旧 snapshot 反解析事实，旧 snapshot 只能作为 migration/backfill 输入。

导出形态：

```text
JsonExportService
  -> export_daily_snapshot(date)
  -> export_report_onion_variants(date)
  -> export_mainline_series(end_date, lookback_days)
  -> export_turnover_rank_series(end_date, lookback_days, limit)
  -> export_snap_ui_payload(route_key, params)
```

这个服务就是你说的“Kettle 类转换层”：输入是 DB 事实和派生表，输出是消费端需要的 JSON。转换规则集中管理，不再散落在业务代码里。

## 数据库表设计

### provider_source_runs

记录每次 provider 拉取：

| 字段 | 说明 |
|---|---|
| id | run id |
| provider | tushare / akshare / tencent / baostock |
| endpoint | daily / index_daily / moneyflow 等 |
| params_json | 请求参数 |
| status | success / partial / failed |
| row_count | 返回行数 |
| started_at / finished_at | 时间 |
| error_message | 错误摘要 |
| payload_hash | 原始返回 hash |

### stock_daily_quotes

个股日线事实：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| ts_code | Tushare 代码 |
| stock_code | 六位代码 |
| name | 名称，可冗余快照 |
| open/high/low/close/pre_close | 价格 |
| change/pct_chg | 涨跌 |
| vol | 成交量，手 |
| amount | 成交额，千元 |
| source_run_id | 来源 |

主键：`(trade_date, ts_code)`。

### index_daily_quotes

指数日线事实：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| index_code | 如 000001.SH / 399001.SZ / 399107.SZ |
| open/high/low/close/pre_close | 点位 |
| change/pct_chg | 涨跌 |
| vol | 成交量 |
| amount | 成交额，千元 |
| source_run_id | 来源 |

注意：深证成指 `399001.SZ` 不等同于深市全 A 成交额；需要和行情软件口径一致时，优先评估 `399107.SZ` 或全市场个股求和。

### stock_daily_basic

每日指标：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| ts_code | 股票 |
| turnover_rate | 换手率 |
| volume_ratio | 量比 |
| pe/pb/ps | 估值 |
| total_mv/circ_mv | 市值 |
| source_run_id | 来源 |

### stock_moneyflow_daily

资金流事实：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| ts_code | 股票 |
| buy/sell small/medium/large/extra_large amount | 分档资金 |
| net_mf_amount | 净流入 |
| source_run_id | 来源 |

### limit_list_daily

涨跌停/炸板事实：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| ts_code | 股票 |
| name | 名称 |
| limit_type | 涨停/跌停/炸板等 |
| status | 封板状态 |
| first_time/last_time/open_times | 打板字段 |
| source_run_id | 来源 |

### market_daily_totals

市场级聚合：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| market_scope | all_a / sh_a / sz_a / bj_a / sh_sz_a |
| total_amount_yi | 成交额，亿元 |
| stock_count | 股票数 |
| source_policy | stock_sum / index_amount / mixed |
| source_run_id | 来源 |

用途：计算“成交额前 50 与两市成交额占比”时，不再临时扫描 JSON。

### turnover_rank_daily

成交额排行派生表：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| rank_scope | all_a / sh_sz_a |
| rank_no | 名次 |
| ts_code | 股票 |
| amount_yi | 成交额，亿元 |
| total_amount_yi | 当日市场成交额 |
| amount_share_pct | 占比 |

用途：支持近 30 天 top50 占比曲线。

### mainline_daily

主线定义事实/派生表：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| primary_mainline | 周期主线 |
| daily_attack_line | 当日主攻线 |
| secondary_mainline | 次强线 |
| competition_mainline | 竞争线 |
| leading_line | 状态机主线 |
| state_code | 启动/发酵/高潮/退潮/冰点等稳定口径 |
| confidence | 置信度 |
| source_policy | state_machine / snapshot_backfill / manual_review |
| evidence_json | 趋势密度、涨停、资金、题材证据 |

### sector_turnover_daily

板块/链路成交额：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| sector_scope_key | 如 green_power_chain |
| display_name | 绿电链 / 电力本体 |
| matched_sector_names | 参与聚合的板块名 JSON |
| sector_turnover_yi | 成交额 |
| market_turnover_yi | 两市成交额 |
| turnover_share_pct | 占比 |
| source_policy | tencent / ths / tushare_sector / manual_mapping |

### mainline_turnover_daily

主线与成交额占比派生表：

| 字段 | 说明 |
|---|---|
| trade_date | 交易日 |
| primary_mainline | 周期主线 |
| turnover_scope_key | 口径 key |
| turnover_scope_label | 展示名 |
| sector_turnover_yi | 主线成交额 |
| market_turnover_yi | 两市成交额 |
| turnover_share_pct | 占比 |
| share_trend_label | 强化/分化/切换/持平 |
| conclusion | 结构化结论 |

### report_runs / report_artifacts

把日报生成与 JSON/markdown 产物纳入索引：

| 表 | 说明 |
|---|---|
| report_runs | 某日期日报生成任务、模式、状态、错误、source_run |
| report_artifacts | snapshot/report onion/full markdown/public payload 的路径、hash、schema_version、是否公开 |

## 查询例子

### 近30天成交额前50占比

```text
DatabaseService.query_top_turnover_share_series(
  end_date="2026-05-12",
  window_days=30,
  limit=50,
)
```

返回：

```json
{
  "window_days": 30,
  "limit": 50,
  "rows": [
    {
      "trade_date": "2026-04-22",
      "top_amount_yi": 5092.78,
      "market_amount_yi": 25788.47,
      "share_pct": 19.75
    }
  ]
}
```

### 近25日主线与成交额占比

```text
DatabaseService.query_mainline_turnover_series(
  end_date="2026-05-12",
  lookback_days=25,
)
```

返回直接给 `mainline_turnover_summary` 和 snap-ui，不再从 25 个 snapshot 文件里拆。

## ETL / Kettle-like 管道

第一期按日批处理，不做复杂 DAG 平台，但要有明确阶段：

```text
1. collect
   TushareProvider 拉 stock/index/daily_basic/moneyflow/limit_list_d

2. load raw/fact
   DatabaseService upsert fact tables

3. derive
   生成 market_daily_totals、turnover_rank_daily、mainline_daily、sector_turnover_daily

4. compose
   生成 mainline_turnover_daily、report context bundle

5. export
   JsonExportService 生成 snapshot/report onion/snap-ui payload

6. publish
   report_artifacts 登记路径、hash、schema_version、visibility
```

失败策略：

- provider 失败要记录到 `provider_source_runs`，不能被 fallback 静默掩盖。
- Tushare 部分成功时，允许 fallback 补齐缺口，但最终 payload 必须说明混合来源。
- derive 失败不覆盖上一版 artifact；report run 标记 `failed` 或 `warning`。
- JsonExportService 对未知 schema version fail closed。

## Cloudflare / Go 后端边界

推荐形态：

```text
Python job runner
  -> pulls Tushare / fallback providers
  -> writes Postgres facts + derived tables
  -> exports JSON artifacts

Go API or Cloudflare Worker
  -> queries Postgres / Hyperdrive
  -> reads registered artifacts
  -> applies auth / entitlement / quota
  -> returns JSON to snap-ui
```

Cloudflare Worker 可以通过 Hyperdrive 连接 Postgres，用于公开查询、轻量 API 和边缘缓存。Worker 不应该直接调用 Tushare，也不应该运行 pandas 或日报主流程。D1 可以存公开 manifest、短期缓存、用户轻量状态，但不要承载全市场行情事实。

这与 `2026-05-10-go-backend-service-boundary-design.md` 对齐：Go/CF 是服务壳和授权边界，Python 仍是数据采集、日报生成和导出核心。

## 迁移计划

### Phase 0：冻结新边界

- 保留 `scripts/market_data/tushare_client.py` 作为唯一 Tushare 初始化入口。
- 给现有 Tushare service 增加 provider health / source run 概念的设计入口。
- 盘点并标记现有 JSON 写入点：哪些是 artifact，哪些是过渡缓存，哪些要迁到 DB。

验收：

- 新代码不得直接新增散落 `json.dump/write_text` 事实输出。
- 所有新增 JSON 输出必须走 JsonExportService 或明确标注为临时 artifact。

### Phase 1：成交额事实库垂直切片

目标只做一个闭环：

```text
Tushare daily(trade_date)
  -> stock_daily_quotes
  -> market_daily_totals
  -> turnover_rank_daily
  -> JsonExportService.export_turnover_rank_series
```

验收：

- 能查询指定日期成交额前 50。
- 能查询近 30 个交易日 top50 / 两市成交额占比。
- 生成的 JSON 与 snap-ui/report 消费契约一致。
- 旧 replay 仍可读取，不因新 DB 缺数据中断。

### Phase 2：主线与成交额占比入库

目标：

- `mainline_daily` 接收现有状态机/主线识别输出。
- `sector_turnover_daily` 接收腾讯/THS/Tushare sector provider 的链路口径结果。
- `mainline_turnover_daily` 替代跨 snapshot 查询。

验收：

- 能查询近 25 日主线定义。
- 能查询周主线。
- 能查询主线成交额占比趋势。
- 2026-05-07 绿电/电力口径仍满足本体链边界，不把算力、锂电错误并入。

### Phase 3：日报 snapshot 从 DB 导出

目标：

- `daily_report_snapshot_io.py` 不再直接拼事实 JSON，而是调用 JsonExportService。
- 旧 frozen/replay 快照仍保留为回放 artifact。

验收：

- 新日期 snapshot 可从 DB 重建。
- report onion publisher 可从 `report_artifacts` 读取 manifest。
- `snap-ui` 的 `mainline-series`、`snapshot-index`、`observation-pool` 逐步切到 DB payload。

### Phase 4：Go/CF 只读查询

目标：

- Go 或 Worker 提供只读 API：日报索引、主线序列、成交额排行序列。
- 权限层只决定返回哪个 artifact/payload，不重新生成日报。

验收：

- Worker/Go 不需要访问本地 `snapshots/*.json`。
- Cloudflare 可通过 Hyperdrive 查询 Postgres。
- D1 只用于公开 manifest/cache，不承担事实库角色。

## 第一版 Done Definition

- Tushare 默认 provider 可拉取股票日线、指数日线、全市场某日成交额排行；旧 provider 仍可 fallback。
- Postgres schema 至少覆盖 `stock_daily_quotes`、`market_daily_totals`、`turnover_rank_daily`、`provider_source_runs`、`report_artifacts`。
- `DatabaseService.query_top_turnover_share_series()` 能返回近 30 天 top50 占比。
- `JsonExportService.export_turnover_rank_series()` 是该 JSON 的唯一出口。
- 新增代码不直接扫描多个 snapshot 文件来回答跨日查询。
- 旧 JSON replay 不被删除，仍可作为 backfill/replay artifact。
- provider 失败、fallback、混合来源能在日志或 source_run 中看见。

## 风险和处理

- Tushare 网关或 token 异常：provider health 显示 `failed`，并提示是否缺少自定义 `__http_url`，不能悄悄变成空数据。
- Tushare 字段单位误用：金额统一入库为原始单位和标准化亿元两种字段，导出层只读标准化字段。
- JSON 与 DB 双写漂移：第一期允许双写 artifact，但事实只认 DB；旧 JSON 只读不更新事实。
- Postgres 本地门槛：提供 Docker Compose 或 `.env.example`，测试层可以用 SQLite adapter，但生产 schema 以 Postgres migration 为准。
- 板块口径污染：主线成交额必须记录 `matched_sector_names` 和 `turnover_scope_key`，渲染层不能二次猜测。
- Cloudflare 边缘限制：Worker 只做 read/query/cache，长任务和 pandas 留在 Python job runner。

## 参考链接

- Tushare skill 目录：[HKUDS/Vibe-Trading Tushare SKILL.md](https://raw.githubusercontent.com/HKUDS/Vibe-Trading/main/agent/src/skills/tushare/SKILL.md)
- Tushare A 股日线：[daily](https://www.tushare.pro/document/2?doc_id=27)，支持按股票或交易日取行情，字段包含 `vol` 和 `amount`。
- Tushare 股票基础信息：[stock_basic](https://tushare.pro/document/2?doc_id=25)。
- Tushare 指数基础信息：[index_basic](https://tushare.pro/document/2?doc_id=94)。
- Tushare 指数日线：[index_daily](https://www.tushare.pro/document/2?doc_id=95)。
- Tushare 每日指标：[daily_basic](https://tushare.pro/document/2?doc_id=32)。
- Tushare 个股资金流：[moneyflow](https://tushare.pro/document/2?doc_id=170)。
- Tushare 涨跌停/炸板：[limit_list_d](https://tushare.pro/document/2?doc_id=298)。
- Cloudflare Hyperdrive：[Connect to PostgreSQL](https://developers.cloudflare.com/hyperdrive/configuration/connect-to-postgres/)。
- Cloudflare D1：[FAQ limits](https://developers.cloudflare.com/d1/reference/faq/)，单库容量和单库串行执行模型更适合轻量/分片场景，不适合作为全市场事实库。
