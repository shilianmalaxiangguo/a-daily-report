# 候选选股轨迹设计

日期：2026-05-27

## 结论

第一版新增 `候选选股轨迹`：日报在给出 T0/T1/T2/T3 分层时，同时说明每只候选使用了哪些输入、满足了哪些条件、卡在哪些条件、走到哪个分支，最后为什么得到当前层级和明日动作。

这不是新的选股评分系统，也不是重写候选生成。它是一个可读、可复盘、可测试的解释层：把现有候选质量、账户建议、主线判断和动作分层串成表格与结构化记录，让用户知道“结合什么参数得到什么结果，然后为什么选它”。

第一版采用 B 方案：

- 日报可见表格覆盖 T0/T1/T2/T3。
- 淘汰对象只做原因分类统计，不展开逐票长表。
- 底层保存结构化 JSON，后续可按样本反馈升级到逐票淘汰轨迹。

## Harness Engineering 启发

本设计继承三个原则：

- 让判断过程对智能体可读：候选不是只留下结论，而是留下输入、条件、分支和动作。
- 让经验沉淀到仓库：偏好、条件、样本反馈不只停留在聊天里，而是进入合同、表格、JSON artifact 和测试。
- 让复盘能反推规则：次日结果出来后，可以定位是市场没有选择、个股没有承接、账户不适配、时间窗口没出现，还是规则本身需要修正。

## In Scope

- 为进入日报分层的 T0/T1/T2/T3 候选生成选股轨迹。
- 轨迹字段覆盖输入事实、条件判断、分支路径、最终层级、明日动作、触发条件、失效条件和缺失数据。
- 日报 Markdown 增加表格展示，首页只放 T0/T1 精简表，附录放完整 T0/T1/T2/T3 表。
- 生成结构化 artifact：`data/candidate-traces/YYYY-MM-DD.json`。
- 淘汰对象只生成原因分类统计，包含原因、数量和最多 3 个代表对象，不生成逐票完整轨迹。
- 与现有 `候选质量与动作分层`、`明日账户建议`、`判断账本` 保持同一语言口径。
- 新增单测覆盖字段合同、Markdown 渲染、缺失数据、淘汰分类和 2026-05-26 样本。

## Out of Scope

- 不重写候选生成流程。
- 不新增复杂总分、权重或排序系统。
- 不追踪全市场所有股票。
- 不给每个淘汰对象生成逐票长表。
- 不改变 T0/T1/T2/T3 的含义。
- 不改变已有账户建议的优先级。
- 不接入线上数据库或发布流程。
- 不把完整行情、K 线数组或原始数据塞进轨迹 artifact。

## Non-goals

- 不保证候选次日一定上涨。
- 不追求一次把所有判断解释到完美。
- 不用长篇理论替代表格字段。
- 不让附录候选抢首页动作建议。
- 不用丰富候选数量制造可参与错觉。
- 不为了未来逐票淘汰能力提前扩大第一版。

## Done Definition

- 任意 T0/T1/T2/T3 候选都能看到：来源池、关键输入、满足条件、未满足或缺失条件、分支结果、明日动作。
- 首页能在两分钟内读完 T0/T1 的精简轨迹。
- 附录能查看完整 T0/T1/T2/T3 轨迹表。
- 结构化 artifact 能保存同一批轨迹，供复盘和后续迭代使用。
- 淘汰对象只显示分类统计，避免日报膨胀。
- 2026-05-26 样本能解释华天科技进入 T0 条件观察，以及步步高、大众公用、红星发展等只作为 T3 观察线索。
- 缺少关键输入时不补假理由，表格明确写 `关键数据不完整` 或 `数据缺失`。
- 测试命令使用 `.generated/venv-py314/bin/python3.14`。

## 用户可见展示

### 首页精简表

首页只展示 T0/T1，目的是先回答明天最重要的对象和理由。

| 层级 | 候选 | 主线/板块 | 为什么进入这一层 | 卡点 | 明日动作 |
|------|------|-----------|------------------|------|----------|
| T0 | 华天科技(002185) | 半导体 | 主线候选保留、账户适配、结构未破 | 早盘承接仍需确认 | 09:50-10:10确认，不满足继续不参与 |
| T1 | 晶方科技(603005) | 半导体 | 主线核心观察，辨识度和趋势仍在 | 账户优先级低于 T0 | 只观察，不抢 T0 动作 |

### 附录完整表

附录展示 T0/T1/T2/T3 的完整轨迹，但仍保持表格化。

| 层级 | 候选 | 来源池 | 主线/板块 | 关键输入 | 满足条件 | 未满足/缺失 | 分支结果 | 明日动作 | 失效条件 |
|------|------|--------|-----------|----------|----------|-------------|----------|----------|----------|
| T0 | 华天科技(002185) | 主线核心候选 | 半导体 | 承接、收盘位置、账户适配、交易窗口 | 主线候选、账户可做、结构未破 | 早盘确认不足 | 条件观察 | 09:50-10:10确认，不满足不参与 | 主线回落或放量不承接 |
| T1 | 晶方科技(603005) | 主线核心候选 | 半导体 | 辨识度、趋势密度、成本适配 | 主线身份较强 | 首页优先级不足 | 主线核心观察 | 不参与，只观察是否重新升级 | 继续弱于 T0 或承接失败 |
| T2 | 新洁能(605111) | 次主线候选 | 半导体 | 板块反馈、相对强度 | 有备选价值 | 核心身份不足 | 次主线观察 | 等待重新进入 T1 | 板块扩散转弱 |
| T3 | 步步高(002251) | 异动线索 | 消费 | 异动、涨停惯性 | 有线索价值 | 不属于当前主线动作 | 观察线索 | 不参与 | 不能转入主线或承接失败 |

### 淘汰分类统计

淘汰对象不展开逐票轨迹，只展示原因分类。

| 淘汰原因 | 数量 | 代表对象 | 处理 |
|----------|------|----------|------|
| 主线不匹配 | 5 | 大众公用、红星发展 | 保留观察，不进入动作分层 |
| 账户不适配 | 2 | 中船特气 | 保留市场身份，不进入 T0 新开仓 |
| 个股承接不足 | 4 | 示例对象 | 等待重新满足条件 |
| 关键数据不完整 | 1 | 示例对象 | 停止给出动作 |

## 结构化 Artifact

文件路径：

```text
data/candidate-traces/YYYY-MM-DD.json
```

第一版 JSON 合同：

```json
{
  "artifact_version": 1,
  "trade_date": "2026-05-26",
  "generated_at": "2026-05-27T00:00:00+08:00",
  "source_report": {
    "path": "reports/2026-05-26_A股日报_完整版.md",
    "variant": "full"
  },
  "visible_scope": "T0_T1_T2_T3",
  "traces": [
    {
      "candidate_id": "2026-05-26-002185",
      "stock_code": "002185",
      "stock_name": "华天科技",
      "tier": "T0",
      "source_pools": ["主线核心候选"],
      "mainline": "半导体",
      "sector": "半导体",
      "key_inputs": [
        {"field": "收盘位置", "value": "结构未破", "source": "candidate_quality"},
        {"field": "账户适配", "value": "1w账户可买一手", "source": "account_context"},
        {"field": "交易窗口", "value": "09:50-10:10", "source": "time_window_contract"}
      ],
      "checks": [
        {
          "check_key": "market_fit",
          "label": "市场条件",
          "result": "部分满足",
          "evidence": "市场不支持强进攻，但允许核心候选条件观察",
          "branch_effect": "不能直接核心进攻"
        },
        {
          "check_key": "mainline_fit",
          "label": "主线条件",
          "result": "满足",
          "evidence": "半导体仍在主线候选内",
          "branch_effect": "保留 T0/T1 比较资格"
        },
        {
          "check_key": "stock_structure",
          "label": "个股结构",
          "result": "部分满足",
          "evidence": "承接未破，但早盘仍需确认",
          "branch_effect": "只能条件观察"
        }
      ],
      "branch_path": [
        "市场条件部分满足",
        "主线候选保留",
        "个股结构未完成确认",
        "账户适配",
        "进入 T0 条件观察"
      ],
      "final_action": "09:50-10:10确认，不满足继续不参与",
      "trigger_condition": "主线承接 + 个股突破或回踩确认",
      "failure_condition": "主线回落或放量不承接",
      "missing_data": [],
      "visible_summary": "主线候选保留、账户适配、结构未破；早盘承接仍需确认。"
    }
  ],
  "eliminated_summary": [
    {
      "reason": "主线不匹配",
      "count": 5,
      "representatives": ["大众公用", "红星发展"],
      "treatment": "保留观察，不进入动作分层"
    }
  ]
}
```

## 字段规则

### `tier`

只允许：

- `T0`：明日账户动作层。
- `T1`：主线核心观察层。
- `T2`：次主线或备选方向层。
- `T3`：观察线索层。

### `checks.result`

只允许：

- `满足`
- `部分满足`
- `未满足`
- `数据缺失`

`数据缺失` 不能被渲染成正向理由。若缺失字段影响 T0/T1 动作，最终动作必须降为条件观察或不参与。

### `branch_path`

`branch_path` 是给人和复盘看的短路径，最多 6 步。每一步必须是交易语言，例如：

- `市场条件部分满足`
- `主线候选保留`
- `账户不适配，不能进入 T0 新开仓`
- `个股承接不足，降为 T3 观察线索`

### `visible_summary`

`visible_summary` 用于首页精简表。必须短，不超过 40 个中文字符；完整解释放在附录表和 JSON。

## 数据流

```text
candidate_quality_samples / market_research_snapshot / account context
  -> candidate trace contract builder
      -> normalize candidate identity
      -> collect key inputs
      -> evaluate visible checks from existing fields
      -> derive tier and branch path
      -> build eliminated summary
  -> candidate quality renderer
      -> front compact trace table
      -> appendix full trace table
  -> candidate trace artifact writer
      -> data/candidate-traces/YYYY-MM-DD.json
  -> replay / review
      -> compare next-day facts with original trace
```

## 代码落点

第一版优先复用现有结构：

- `scripts/selection/candidate_quality_contracts.py`：候选质量合同可增加 `trace` 字段。
- `scripts/report/candidate_quality_renderer.py`：增加轨迹表渲染函数，复用现有 Markdown 转义。
- `scripts/report/action_plan_nodes.py`：在 `candidate_quality` 节点可开关展示轨迹表。
- `scripts/report/candidate_snapshot_contract.py`：必要时补充首页 T0/T1 精简轨迹来源。
- `scripts/report/decision_ledger.py`：只在强跟踪样本里保留轨迹引用或摘要，不复制完整 artifact。

如果 `candidate_quality_contracts.py` 因轨迹字段明显膨胀，可以新增小模块：

```text
scripts/selection/candidate_trace_contracts.py
```

该模块只负责轨迹合同，不负责重新筛股、重新排序或改变明日动作。

## 缺失数据与异常处理

- 缺少候选代码或名称：仍可渲染为 `观察对象`，但 artifact 记录 `missing_data`。
- 缺少主线或板块：表格写 `未归类`，不作为正向理由。
- 缺少账户适配：不能进入 T0 新开仓，表格写 `账户数据缺失`。
- 缺少交易窗口：最终动作只能写观察或不参与。
- 缺少关键数据且会影响动作：写 `关键数据不完整`，不生成参与动作。
- Markdown 表格单元格必须清洗换行和 `|`，避免破坏表格。

## 测试

使用固定 Python 解释器：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_contracts
.generated/venv-py314/bin/python3.14 -m unittest tests.test_candidate_quality_renderer
.generated/venv-py314/bin/python3.14 -m unittest tests.test_action_plan_renderer
.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime
```

新增或扩展测试：

- 候选合同能生成 `trace`，包含 `key_inputs`、`checks`、`branch_path`、`final_action`。
- `checks.result` 只允许受控值。
- 缺少账户适配时，T0 新开仓动作被降为条件观察或不参与。
- 渲染器能输出首页精简表和附录完整表。
- Markdown 单元格能清洗换行和 `|`。
- 淘汰分类统计只显示分类、数量和最多 3 个代表对象。
- 2026-05-26 样本能收口为华天科技 T0 条件观察，步步高、大众公用、红星发展只作为 T3 观察线索。
- 结构化 artifact 能通过字段完整性检查。

## 后续实现任务边界

后续实现可拆为四个互不抢文件的任务：

1. 合同任务：扩展候选合同，产出 `trace` 字段和淘汰分类。
2. 渲染任务：把 `trace` 渲染为首页精简表和附录完整表。
3. Artifact 任务：写入 `data/candidate-traces/YYYY-MM-DD.json`，并加入字段检查。
4. 验收任务：补 2026-05-26 样本测试和报告运行回归。

四个任务都不得改变 T0/T1/T2/T3 的既有含义，不得新增复杂评分系统。

## 1.1 迭代触发条件

第一版上线后，如果出现以下反馈，再升级：

- 用户想知道某只未出现在 T0/T1/T2/T3 的股票为什么被排除。
- 淘汰分类数量过大，无法解释主要差异。
- 次日复盘无法定位错误来自哪个条件。
- 多次出现同一类误判，需要把淘汰分类升级为逐票轨迹。

升级方向是 C 方案：给最终淘汰对象也生成逐票轨迹，但只在复盘或单独 MD 中展开，不挤占日报首页。
