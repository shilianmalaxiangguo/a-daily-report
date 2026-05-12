# 日报事实库与 Cloudflare 免费优先导出管道设计

日期：2026-05-12

## 结论

第一阶段按 `Cloudflare 免费优先` 执行：能白嫖 CF 就先白嫖 CF。当前项目是小范围日报、复盘、snap-ui 查询，不需要在没有收益前买服务器或强上正式 Postgres。

新的判断：

```text
Python 本地/CI job runner
  -> Tushare 默认数据源 + 旧 provider fallback
  -> MarketDataService 统一查询
  -> DatabaseService 统一写入
       -> 第一阶段：Cloudflare D1 compact facts / derived tables
       -> R2 raw payloads + JSON artifacts
       -> 未来可切：Postgres / Go backend
  -> JsonExportService
  -> Cloudflare Pages + Workers API + D1/R2
```

事实源不再是散落 JSON 文件，而是 `DatabaseService` 这一层。第一阶段它背后可以是 D1，因为你的实际范围小、查询窗口可控、主要是日报派生结果；未来数据量、用户量或收益起来后，再把同一层换成 Postgres。

换句话说：`Postgres-compatible boundary` 保留，`Postgres server` 不现在买。

## In Scope

- 重写架构为 CF 免费优先：Pages、Workers、D1、R2 优先承载。
- 明确哪些数据放 D1、哪些放 R2、哪些只本地/CI 临时处理。
- 保留 Tushare 默认 provider，旧 provider 作为 fallback/specialized adapter。
- 设计 `DatabaseService`，让外部不感知 D1、SQLite、Postgres 的差异。
- 设计 `JsonExportService`，让 JSON 成为受控导出产物，不再到处散写。
- 给出未来接 Go / Postgres / Hyperdrive 的升级路径，但不作为第一阶段前提。

## Out of Scope

- 不买服务器。
- 不现在搭正式 Postgres。
- 不把全量 Tushare 原始宽表都塞进 D1。
- 不删除现有 AkShare、BaoStock、QuickTiny、腾讯/同花顺等路径。
- 不重写日报生成主链路、Chanlun、中枢、report onion 或 snap-ui。

## Non-goals

- 不把 D1 当无限数据仓库。
- 不让 Worker 直接跑 Tushare、pandas 或日报生成。
- 不让 Worker 存 Tushare token。
- 不通过扫描多个旧 snapshot JSON 回答新跨日需求。
- 不为了未来 Go 服务提前扩大当前 PR。

## Cloudflare 免费额度判断

Cloudflare 当前免费额度足够支撑第一阶段：

| 产品 | 免费额度 | 在本项目里的角色 | 风险 |
|---|---:|---|---|
| Pages | 静态资产请求免费且不限量；Functions 计入 Workers 请求 | 部署 `snap-ui` 静态前端 | SSR/Functions 多了会吃 Workers 请求 |
| Workers | 100,000 请求/天，10ms CPU/请求 | 轻 API、鉴权、读取 D1/R2 | 不跑重计算，不跑 pandas |
| D1 | 5M rows read/天，100k rows written/天，5GB 总存储；免费单库 500MB | compact facts、派生表、索引、用户轻状态 | 单库小、单库串行，需要控制表宽和窗口 |
| R2 | 10GB-month，1M Class A/月，10M Class B/月，公网 egress 免费 | JSON artifacts、raw payload gzip、完整日报 | 大量未缓存读取会消耗 Class B |
| Hyperdrive | 100,000 database queries/天 | 未来 Worker 连接免费/付费 Postgres | 第一阶段不用，除非接 Neon/Supabase |

结论：当前数据规模和访问量下，CF 免费组合足够用。D1 不适合无限存全市场多年宽表，但适合存“压缩后的事实 + 派生结果 + 最近窗口”。R2 适合存完整 JSON、原始 payload、日报 artifacts。

## 为什么第一阶段 D1 可以做事实库

之前说“Postgres 是正式事实库”是面向长期 SaaS 的保守设计。按你现在的目标，要改成更现实的分层：

| 层 | 第一阶段 | 未来升级 |
|---|---|---|
| 代码事实边界 | `DatabaseService` | 不变 |
| 实际在线数据库 | D1 | Postgres |
| 原始大 payload | R2 gzip JSON | R2 / object storage / Postgres JSONB |
| 查询服务 | Workers | Workers 或 Go API |
| 重计算 | 本地 Python / CI | Python worker / Go job orchestrator |

D1 可以先承接“项目范围内的正式事实”，但有三条边界：

- 只存当前报表和查询真正要用的 compact 字段，不把全量宽表无脑落 D1。
- 重计算在 Python job runner 做完，D1 只承接结果和可快速查询的事实。
- 每个写入都有 `source_run_id`、`schema_version`、`source_policy`，未来迁 Postgres 时可重放。

## 数据与存储表

| 数据 | 默认调用方式 | 第一阶段存储 | D1 表/对象 | R2 对象 | 未来 Postgres/Go |
|---|---|---|---|---|---|
| Tushare 初始化 | `scripts/market_data/tushare_client.py` | 不上 CF | 无 | 无 | 不变 |
| 股票基础信息 | `pro.stock_basic()` | D1 | `stock_basic_current` | `raw/tushare/stock_basic/*.json.gz` | `stock_basic` |
| 交易日历 | `pro.trade_cal()` | D1 | `trade_calendar` | `raw/tushare/trade_cal/*.json.gz` | `trade_calendar` |
| 全市场日线 | `pro.daily(trade_date=...)` | D1 compact + R2 raw | `stock_daily_quotes_recent` | `raw/tushare/daily/{date}.json.gz` | `stock_daily_quotes` |
| 单票复权 K 线 | `ts.pro_bar(api=pro, ts_code=...)` | R2 artifact + D1 索引 | `stock_kline_artifacts` | `kline/{code}/{date_range}.json` | `stock_daily_adjusted_quotes` |
| 指数基础信息 | `pro.index_basic()` | D1 | `index_basic_current` | `raw/tushare/index_basic/*.json.gz` | `index_basic` |
| 指数日线 | `pro.index_daily()` / `pro_bar` | D1 | `index_daily_quotes_recent` | `raw/tushare/index_daily/{date}.json.gz` | `index_daily_quotes` |
| 每日指标 | `pro.daily_basic(trade_date=...)` | 第一阶段只存用到字段 | `stock_daily_basic_recent` | `raw/tushare/daily_basic/{date}.json.gz` | `stock_daily_basic` |
| 资金流 | `pro.moneyflow(trade_date=...)` | D1 存榜单/摘要，R2 存 raw | `moneyflow_rank_daily` | `raw/tushare/moneyflow/{date}.json.gz` | `stock_moneyflow_daily` |
| 涨跌停/炸板 | `pro.limit_list_d(trade_date=...)` | D1 | `limit_list_daily` | `raw/tushare/limit_list_d/{date}.json.gz` | `limit_list_daily` |
| 成交额前50 | 从 `daily` 派生 | D1 | `turnover_rank_daily` | `exports/turnover/top50/{date}.json` | materialized view |
| 两市成交额 | 从全市场日线求和，指数口径只作校验 | D1 | `market_daily_totals` | `exports/market/totals/{date}.json` | `market_daily_totals` |
| 近30天 top50 占比 | D1 查询/导出 | D1 + R2 | `turnover_share_series` | `exports/turnover/top50-share/latest.json` | query/materialized view |
| 主线定义 | 现有状态机/主线识别 | D1 | `mainline_daily` | `exports/mainline/{date}.json` | `mainline_daily` |
| 主线成交额占比 | 主线口径 + 板块成交额 | D1 | `mainline_turnover_daily` | `exports/mainline-turnover/latest.json` | `mainline_turnover_daily` |
| 日报公开版 | `JsonExportService` | R2 + D1 索引 | `report_artifacts` | `reports/{date}/public-brief.json` | `report_artifacts` |
| 日报完整版 | `JsonExportService` | R2 私有对象 + D1 索引 | `report_artifacts` | `reports/{date}/full.json` | `report_artifacts` |
| 运行/provider 日志 | Python job runner | D1 摘要 + R2 raw | `provider_source_runs` | `logs/provider/{run_id}.json` | `provider_source_runs` |
| 用户、收藏、额度 | Worker API | D1 | `users`、`favorites`、`quota_counters` | 无 | Go/Postgres 可接管 |

## D1 schema 第一阶段

D1 只建小而有用的表，不建全量数据仓库。

### provider_source_runs

记录每次拉数、导出、fallback：

```text
id
trade_date
provider
endpoint
params_json
status
row_count
duration_ms
error_message
raw_r2_key
created_at
```

### stock_daily_quotes_recent

只存最近窗口需要的 compact 字段：

```text
trade_date
ts_code
stock_code
name
open
high
low
close
pct_chg
amount_yi
vol
source_run_id
```

保留策略：

- 默认保留最近 250 个交易日。
- 如果 D1 体积接近 400MB，先缩到 120 个交易日。
- 完整 raw 每日行情留在 R2，可重建。

### market_daily_totals

```text
trade_date
market_scope
total_amount_yi
stock_count
source_policy
source_run_id
```

`market_scope` 第一阶段支持：

- `all_a`
- `sh_sz_a`
- `sh_a`
- `sz_a`
- `bj_a`

### turnover_rank_daily

```text
trade_date
rank_scope
rank_no
ts_code
stock_code
name
amount_yi
total_amount_yi
amount_share_pct
source_run_id
```

只存 top N，不存全市场排行。第一阶段 `N=100`，UI 默认展示 top50。

### turnover_share_series

预计算 UI 直接读的窗口结果：

```text
series_key
end_date
window_days
rank_limit
payload_json
generated_at
source_run_ids_json
```

`payload_json` 是小 JSON，避免 Worker 每次现算 30 天聚合。

### mainline_daily

```text
trade_date
primary_mainline
daily_attack_line
secondary_mainline
competition_mainline
leading_line
state_code
confidence
evidence_json
source_policy
source_run_id
```

### mainline_turnover_daily

```text
trade_date
primary_mainline
turnover_scope_key
turnover_scope_label
matched_sector_names_json
sector_turnover_yi
market_turnover_yi
turnover_share_pct
share_trend_label
conclusion
source_run_id
```

### report_artifacts

```text
trade_date
variant
visibility
r2_key
content_hash
schema_version
source_run_id
created_at
```

`variant` 包括：

- `public-brief`
- `private-brief`
- `full`
- `snapshot`
- `snap-ui-payload`

## R2 对象布局

R2 是完整 JSON 和 raw payload 的家。D1 存索引，R2 存内容。

```text
raw/
  tushare/
    daily/2026-05-12.json.gz
    daily_basic/2026-05-12.json.gz
    moneyflow/2026-05-12.json.gz
    limit_list_d/2026-05-12.json.gz

exports/
  turnover/top50/2026-05-12.json
  turnover/top50-share/latest.json
  mainline/2026-05-12.json
  mainline-turnover/latest.json

reports/
  2026-05-12/public-brief.json
  2026-05-12/private-brief.json
  2026-05-12/full.json
  2026-05-12/snapshot.json

logs/
  provider/{run_id}.json
  jobs/{job_id}.json
```

R2 读取策略：

- Worker 优先读 D1 小 payload。
- 大 JSON 通过 R2 返回，并加 cache header。
- snap-ui 高频页面尽量读 `exports/*/latest.json`。
- 完整日报、历史 raw、调试日志不走高频 API。

## 服务边界

### MarketDataService

职责：

- 默认 Tushare，旧 provider fallback。
- 不把 pandas DataFrame 泄露给业务层。
- 每次调用返回 records + source metadata。
- provider 失败必须可见，不能 fallback 后假装全成功。

建议接口：

```text
get_stock_daily_quotes(trade_date, ts_codes=None)
get_index_daily_quotes(trade_date, index_codes=None)
get_stock_daily_basic(trade_date)
get_stock_moneyflow(trade_date)
get_limit_list(trade_date)
get_market_turnover_rank(trade_date, limit=100)
get_stock_kline(ts_code, start_date, end_date, adj="qfq")
```

### DatabaseService

职责：

- 对业务层隐藏 D1/SQLite/Postgres 差异。
- 第一阶段主实现是 `D1DatabaseService`。
- 本地测试可用 `SQLiteDatabaseService`。
- 未来收益后可接 `PostgresDatabaseService`。

建议接口：

```text
save_provider_source_run(run)
upsert_stock_daily_quotes_recent(rows)
upsert_market_daily_totals(rows)
upsert_turnover_rank_daily(rows)
upsert_mainline_daily(row)
upsert_mainline_turnover_daily(row)
save_report_artifact(row)

query_top_turnover_share_series(end_date, window_days=30, limit=50)
query_mainline_history(end_date, lookback_days=25)
query_mainline_turnover_series(end_date, lookback_days=25)
```

### JsonExportService

职责：

- 唯一负责生成 JSON artifact。
- 输出写 R2，索引写 D1。
- 每个 JSON 带 `schema_version`、`generated_at`、`source_run_ids`、`query_window`。

建议接口：

```text
export_turnover_rank_series(end_date, window_days=30, limit=50)
export_mainline_series(end_date, lookback_days=25)
export_mainline_turnover_series(end_date, lookback_days=25)
export_report_payloads(date)
export_snap_ui_payload(route_key, params)
```

## ETL / Kettle-like 管道

第一阶段不做复杂 DAG 平台，只做清晰批处理。

```text
1. collect
   Python job runner 调 Tushare / fallback provider

2. normalize
   DataFrame -> domain records，统一金额单位、日期、代码

3. persist
   R2 保存 raw gzip
   D1 保存 compact facts / provider_source_runs

4. derive
   生成 market_daily_totals、turnover_rank_daily、mainline_daily、mainline_turnover_daily

5. export
   JsonExportService 写 R2 exports/reports
   D1 report_artifacts 登记索引

6. serve
   Pages 承载 snap-ui
   Worker 读 D1/R2 返回 API
```

关键点：

- Tushare token 只在 Python job runner，不进 Worker。
- Worker 不现算 30 天复杂聚合，读预计算结果。
- D1 每日写入控制在 100k rows 内。
- raw 大数据进 R2，不把 D1 撑爆。

## Cloudflare API 形态

第一阶段用 Workers，不上 Go。

```text
GET /api/reports
GET /api/reports/:date
GET /api/reports/:date/variant/:variant
GET /api/turnover/top50-share?window=30
GET /api/mainline-series?lookback=25
GET /api/mainline-turnover?lookback=25
GET /api/stocks/:code/kline
GET /api/provider-runs/:id
```

Worker 规则：

- 小响应直接从 D1 返回。
- 大 payload 根据 `report_artifacts.r2_key` 从 R2 读。
- 公共版只返回 `visibility=public`。
- 私有/完整版后续再加 D1 user/session/entitlement。

## Go / Postgres 升级路径

Go 不是第一阶段必需。没有收益前，Go 后端会带来部署成本和服务维护成本。

未来触发条件：

- D1 单库接近 500MB，且滚动窗口压缩仍不够。
- D1 rows read/write 经常触顶。
- 用户权限、订阅、额度变复杂。
- 主动个股查询并发上来，需要队列、任务调度、日志后台。
- 需要完整历史宽表查询，而不是最近窗口和预计算结果。

升级方式：

```text
Phase CF-Free:
  Worker -> D1/R2

Phase Free-Postgres:
  Worker -> Hyperdrive -> Neon/Supabase free Postgres
  R2 仍存 artifacts

Phase Paid/SaaS:
  Go API -> Postgres
  Worker/Pages 仍可做前置和缓存
  Python job runner 继续负责 Tushare/日报生成
```

要点：

- `DatabaseService` 接口不变。
- D1 表结构尽量和 Postgres 表名/字段兼容。
- 所有 artifact 用 R2 key，不绑定本地路径。
- Go 以后读同一套 `report_artifacts` 和事实表。

## 迁移计划

### Phase 0：重写边界

第一期执行范围：

- 只接 D1 本地/远端 migration 的最小表。
- 只接 R2 artifact writer 的抽象接口和本地文件替身。
- 只打通成交额 top50 占比，不同时迁移主线、report onion、用户系统。

- 保留 `scripts/market_data/tushare_client.py` 为唯一 Tushare 初始化入口。
- 明确新增 JSON 只能走 `JsonExportService` 或 R2 artifact writer。
- 新增 `DatabaseService` 接口，第一实现指向 D1，测试实现指向 SQLite。

验收：

- 新代码不再新增散落 `json.dump/write_text` 事实输出。
- D1/R2/SQLite/Postgres 的角色在文档和接口中明确。

### Phase 1：成交额 top50 免费闭环

目标：

```text
Tushare daily(trade_date)
  -> R2 raw/tushare/daily/{date}.json.gz
  -> D1 stock_daily_quotes_recent
  -> D1 market_daily_totals
  -> D1 turnover_rank_daily
  -> D1 turnover_share_series
  -> R2 exports/turnover/top50-share/latest.json
  -> Worker API
```

验收：

- 能查询指定日期成交额前 50。
- 能查询近 30 个交易日 top50 / 两市成交额占比。
- D1 每日写入不超过 100k rows。
- Worker API 不扫描旧 snapshot 文件。

### Phase 2：主线与成交额占比入库

目标：

- `mainline_daily` 接收现有主线识别结果。
- `mainline_turnover_daily` 接收主线成交额口径。
- `exports/mainline-turnover/latest.json` 给 snap-ui 和日报消费。

验收：

- 能查询近 25 日主线定义。
- 能查询周主线。
- 能查询主线成交额占比。
- 2026-05-07 绿电/电力口径仍不污染算力、锂电。

### Phase 3：report artifacts 上 R2

目标：

- report onion 产物写 R2。
- D1 `report_artifacts` 只存索引。
- Worker 根据权限返回 public/private/full。

验收：

- snap-ui 不需要直读本地 `reports/` 或 `snapshots/`。
- 公共版不泄露 full payload。
- replay artifact 仍可本地保留。

### Phase 4：用户与轻 SaaS

目标：

- D1 增加 `users`、`sessions`、`favorites`、`quota_counters`。
- 默认免费样本不扣额度。
- 主动查询走 quota。

验收：

- Free 用户可看公开日报和默认样本。
- Pro/测试用户可看完整版。
- 不买服务器仍能跑闭环。

## 第一版 Done Definition

- Tushare 默认 provider 能拉全市场日线并生成成交额 top50。
- D1 schema 覆盖 `provider_source_runs`、`stock_daily_quotes_recent`、`market_daily_totals`、`turnover_rank_daily`、`turnover_share_series`、`report_artifacts`。
- R2 保存 raw daily payload 和导出 JSON。
- Worker API 能返回近 30 天 top50 占比。
- 新路径不扫描多个 snapshot JSON。
- 旧 replay/snapshot 文件不删除，作为回放和 backfill 输入。
- 代码层保留 `DatabaseService`，未来可换 Postgres。

## 风险和处理

- D1 写入超 100k/天：只存 compact facts；top rank 存 top100；宽表 raw 去 R2。
- D1 单库接近 500MB：缩短 recent window，或按年份/模块拆 D1，或升级免费 Postgres。
- Worker CPU 超限：Worker 只读预计算结果，不现算 pandas/窗口聚合。
- R2 Class B 读多：热门 JSON 加 cache header，snap-ui 优先读小 payload。
- Tushare 网关异常：provider run 记录 `failed`，提示是否缺 `pro._DataApi__http_url`。
- Tushare 单位误用：入库统一存 `amount_yi`，raw payload 进 R2 可追溯。
- D1 与未来 Postgres 漂移：迁移脚本以 `DatabaseService` records 和 R2 raw 重放，不靠 markdown 反推。

## 参考链接

- Tushare skill 目录：[HKUDS/Vibe-Trading Tushare SKILL.md](https://raw.githubusercontent.com/HKUDS/Vibe-Trading/main/agent/src/skills/tushare/SKILL.md)
- Tushare A 股日线：[daily](https://www.tushare.pro/document/2?doc_id=27)
- Tushare 股票基础信息：[stock_basic](https://tushare.pro/document/2?doc_id=25)
- Tushare 指数基础信息：[index_basic](https://tushare.pro/document/2?doc_id=94)
- Tushare 指数日线：[index_daily](https://www.tushare.pro/document/2?doc_id=95)
- Tushare 每日指标：[daily_basic](https://tushare.pro/document/2?doc_id=32)
- Tushare 个股资金流：[moneyflow](https://tushare.pro/document/2?doc_id=170)
- Tushare 涨跌停/炸板：[limit_list_d](https://tushare.pro/document/2?doc_id=298)
- Cloudflare Workers pricing：[Workers Free 100k requests/day](https://developers.cloudflare.com/workers/platform/pricing/)
- Cloudflare D1 pricing：[D1 rows/storage free tier](https://developers.cloudflare.com/d1/platform/pricing/)
- Cloudflare D1 limits：[D1 database/storage/concurrency limits](https://developers.cloudflare.com/d1/platform/limits/)
- Cloudflare R2 pricing：[R2 free tier and egress](https://developers.cloudflare.com/r2/pricing/)
- Cloudflare Hyperdrive pricing：[Hyperdrive free database queries](https://developers.cloudflare.com/hyperdrive/platform/pricing/)
- Cloudflare Pages Functions pricing：[Pages static requests and Functions quota](https://developers.cloudflare.com/pages/functions/pricing/)
