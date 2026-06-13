# Daily Decision Ledger Design

日期：2026-05-13

## 结论

第一阶段新增本地判断账本：日报生成流程先把“极度看好名单”转成可测试、可重跑、可 diff 的判断样本 artifact，再由报告、复盘列表和 PostgreSQL 导入链路消费。数据库不作为新逻辑的第一写入点。

判断样本不是普通观察票，也不是确定性预测。它必须携带三层假设：个股形态、所属板块候选、等待验证的市场演变分支。25 个交易日结束后，每个样本必须有周期复盘验收结论，用来判断哪条规则保留、哪条规则修正。

## In Scope

- 从日报“极度看好名单”生成判断样本。
- 每个判断样本记录三层假设：个股形态假设、所属板块候选、市场演变分支。
- 同一股票在同一 25 个交易日周期内只创建一个 tracking case，多次被日报点名时追加 mention。
- 本地源 artifact 放在 `data/decision-ledger/`。
- 每个交易日生成 `data/decision-ledger/YYYY-MM-DD.json`。
- 同步刷新 `data/decision-ledger/index.json`。
- `index.json` 支持 `latest_trade_date`、`available_trade_dates`、`by_stock_code`。
- 记录样本验证状态：等待市场选择、市场选择确认、真正失败、提前淘汰后继续走强、周期结束。
- 市场选择确认必须记录确认日期和确认证据。
- 25 个交易日结束必须产生周期复盘验收结论。
- 单测覆盖字段完整性、状态迁移、索引完整性和周期复盘验收分类。

## Out of Scope

- 不把全量观察池全部转成 25 日强追踪样本。
- 不把判断账本直接写入数据库。
- 不在第一阶段实现数据库 schema migration 或线上同步 worker。
- 不改写前端页面结构。
- 不把 Tushare、行情 raw payload 或全市场 K 线塞进判断账本。
- 不把判断样本等同于买入指令。

## Non-goals

- 不追求第一版自动判断所有复杂趋势命运。
- 不用单日涨跌给样本贴胜负标签。
- 不把判断账本当市场数据仓库。
- 不为了未来 SaaS 提前引入用户、订阅、权限或管理后台。
- 不用文章式理论长文进入日报主链，所有结论必须字段化。

## Domain Contract

关键领域词以 `CONTEXT.md` 和 `wiki/交易思想/判断样本与市场演变.md` 为准：

- `判断样本`：由日报选出、携带判断假设、需要被后续市场行为验证的股票案例。
- `三层假设`：个股形态假设、所属板块候选、等待哪个市场演变分支验证。
- `板块关系状态`：替代、继承、混沌接力、交替竞争、暂未分出。
- `等待市场选择`：个股结构未坏，但所属方向尚未被资金明确选择。
- `市场选择确认`：所属板块被资金选择，且个股自身承接或强度跟上。
- `真正失败`：所属方向持续失去选择，且个股自身结构破坏或承接失败。
- `周期复盘验收`：25 个交易日结束时的受控结论。

## Data Flow

```text
daily report generation
  -> candidate selection / conviction list
  -> decision ledger builder
      -> load previous index
      -> create or update 25-day tracking case
      -> append report mention
      -> evaluate current validation state
      -> write daily snapshot
      -> refresh index
  -> report/replay lists read decision-ledger artifact
  -> later: validated rows import to PostgreSQL
```

## JSON Contract

### `data/decision-ledger/YYYY-MM-DD.json`

```json
{
  "artifact_version": 1,
  "trade_date": "2026-05-12",
  "generated_at": "2026-05-13T00:00:00+08:00",
  "source_report": {
    "path": "reports/2026-05-12_A股日报_完整版.md",
    "variant": "full"
  },
  "cases": [
    {
      "case_id": "2026-05-12-601991-01",
      "stock_code": "601991",
      "stock_name": "大唐发电",
      "first_seen_trade_date": "2026-05-12",
      "cycle_start_trade_date": "2026-05-12",
      "cycle_day": 1,
      "cycle_length_trade_days": 25,
      "mentions": [
        {
          "mention_trade_date": "2026-05-12",
          "rank": 1,
          "source_section": "极度看好名单",
          "reason": "趋势形态匹配，等待电力方向是否被市场选择。"
        }
      ],
      "hypothesis": {
        "stock_setup": "趋势性 + 前期活跃 + 高位异动后承接",
        "sector_candidate": "电力",
        "market_branch": "指数高位停顿轮动",
        "sector_relationship_state": "混沌接力"
      },
      "validation": {
        "status": "等待市场选择",
        "selection_confirmed_date": null,
        "selection_confirmed_evidence": null,
        "sector_selection_evidence": null,
        "stock_acceptance_evidence": null
      },
      "trend_fate": {
        "label": null,
        "elimination_event": null,
        "missed_upside_after_elimination": null
      },
      "cycle_acceptance": {
        "status": "open",
        "final_label": null,
        "reason": null,
        "iteration_note": null
      }
    }
  ]
}
```

### `data/decision-ledger/index.json`

```json
{
  "artifact_version": 1,
  "latest_trade_date": "2026-05-12",
  "available_trade_dates": ["2026-05-12"],
  "snapshots": [
    {
      "trade_date": "2026-05-12",
      "path": "data/decision-ledger/2026-05-12.json",
      "case_count": 1,
      "open_case_count": 1
    }
  ],
  "by_stock_code": {
    "601991": [
      {
        "case_id": "2026-05-12-601991-01",
        "stock_name": "大唐发电",
        "cycle_start_trade_date": "2026-05-12",
        "latest_trade_date": "2026-05-12",
        "status": "等待市场选择",
        "snapshot_path": "data/decision-ledger/2026-05-12.json"
      }
    ]
  }
}
```

## State Rules

- 进入判断账本：必须来自“极度看好名单”，且具备三层假设。
- 同周期重复点名：不新建 case，只追加 `mentions`。
- 周期结束后再次点名：关闭旧 case，创建新 25 日 case。
- 等待市场选择：个股结构未破坏，但所属方向尚未被市场明确选择。
- 市场选择确认：所属板块被资金选择，且个股承接或强度跟上；必须记录确认日期和确认证据。
- 真正失败：所属方向持续失去选择，且个股自身结构破坏或承接失败。
- 提前淘汰后继续走强：系统移除样本后，同周期内样本继续走强，必须产生迭代修正。

## Cycle Acceptance Labels

每个 25 交易日 case 结束时必须落到以下五类之一：

- `市场选择确认后趋势兑现`
- `等待市场选择但周期未验证`
- `市场分支未选择且个股假设保留`
- `真正失败`
- `提前淘汰后继续走强`

## Report And Replay Contract

第一版报告和复盘列表需要能消费判断账本结构：

- 展示今日极度看好判断样本。
- 展示每个样本进入名单的日报日期和理由。
- 展示样本处于 25 个交易日周期的第几日。
- 展示等待市场选择、市场选择确认、真正失败等状态。
- 展示确认日期和确认证据。
- 展示单只股票的历史判断周期和重复点名记录。
- 展示周期复盘验收结论和迭代修正。

## Testing

- Python 单测：从 fake report candidate input 生成 daily snapshot。
- Python 单测：同一股票同周期重复点名只追加 mention。
- Python 单测：25 日后仍被点名时关闭旧 case 并创建新 case。
- Python 单测：等待市场选择不能被单日未涨判为失败。
- Python 单测：市场选择确认必须同时具备板块证据和个股证据。
- Python 单测：真正失败必须同时具备板块路径失去选择和个股结构破坏或承接失败。
- Python 单测：周期结束必须生成五类验收结论之一。
- Python 单测：`index.json` 包含 `latest_trade_date`、`available_trade_dates`、`by_stock_code`。
- Python 单测：报告和复盘列表能读到 judgment ledger index 和最新 snapshot。

## Done Definition

- 新增正式判断账本 spec。
- `CONTEXT.md` 和 LLM Wiki 已记录领域词，避免后续语言漂移。
- 第一版实现能生成 `data/decision-ledger/YYYY-MM-DD.json` 和 `data/decision-ledger/index.json`。
- 新增单测覆盖字段完整性、状态迁移、周期验收和索引。
- 报告和复盘列表读取前有 contract check，缺少判断账本关键字段时失败。
- 不写线上发布链路，直到本地 artifact、PostgreSQL 导入和测试稳定。
