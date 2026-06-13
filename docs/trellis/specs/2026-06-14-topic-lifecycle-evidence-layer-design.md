# 题材生命周期证据层设计

## 文档定位

本 spec 定义日报如何把“题材从启动到退潮的证据过程”沉淀为可复用判断样本。目标不是新增后台，也不是把日报写成一正一反的辩论，而是让系统记住每个题材的生命周期证据：它如何启动、如何扩散、第一次分歧如何表现、哪些事实验证了它、哪些事实压缩或证伪了它。

核心判断：题材没有天然固定寿命，只有证据驱动的阶段变化。系统不能输出“某题材还能炒 N 天”这种伪精确结论；系统应该输出“当前处于哪个阶段、下一步要看什么、什么事实出现后不再参与”。

## 背景

外部 Trading Review Wiki 的可取之处不在桌面工作台，也不在多角色辩论，而在它把题材、个股、订单、客户、政策、澄清、价格验证拆成可回看、可替代、可证伪的事实层。这个方向可以服务本仓库的日报：当某个题材再次出现时，日报不只看今天热度，还能回看类似题材过去的启动、扩散、分歧、退潮和失效样本。

本仓库已有基础：

- `wiki/` 保存稳定交易知识和字段化规则。
- `data/decision-ledger/` 保存明日参与预演和 25 个交易日跟踪样本。
- `data/candidate-traces/` 保存候选进入、淘汰和最终动作路径。
- `realtime_tag_evidence_snapshot` 统一行业、概念、板块、热榜和反证信息。
- `knowledge_hits` 已能说明日报命中了哪些经验规则。

缺口是：这些数据还没有形成“题材生命周期卡”。因此日报容易只回答今天可不可做，而无法积累“这类题材通常怎样从可做变成不做”的经验。

## In Scope

- 新增题材生命周期证据层的设计契约。
- 第一版生成本地 artifact：`data/topic-lifecycle/YYYY-MM-DD.json` 和 `data/topic-lifecycle/index.json`。
- 每张题材卡记录：
  - 题材名称、别名、采用名称和主攻分支。
  - 生命周期阶段。
  - 启动催化、资金证据、核心标的、扩散证据。
  - 分歧证据、承接证据、反证信息和失效条件。
  - 当前是否允许进入明日计划。
  - 下一交易日需要验证什么。
  - 与历史相似题材或旧样本的关系。
- 日报只消费压缩后的判断：
  - 当前阶段。
  - 明日看点。
  - 参与资格。
  - 失效条件。
  - 对候选数量和候选分层的影响。
- 题材生命周期更新可以进入 `知识复利提示`，但第一版不自动改写 wiki 正文。
- 第一版只使用已有日报数据、tag 快照、判断账本、候选轨迹和 replay 事实，不新增外部数据源。

## Out of Scope

- 不做后台管理系统。
- 不做新的桌面 UI 或 Web 页面。
- 不引入向量数据库、图数据库或新的长期服务。
- 不把全部历史题材一次性回填。
- 不把题材生命周期写成固定天数统计。
- 不让题材生命周期替代实时行情、主线确认、个股结构、账户条件和买入资格。
- 不把反方观点强行塞进日报正文。
- 不自动修改正式 `wiki/` 节点。
- 不改写现有 `decision-ledger` 和 `candidate-traces` 的第一写入逻辑。

## Non-goals

- 不是预测题材还能持续几天。
- 不是做一正一反辩论模板。
- 不是给每个热点生成长文档。
- 不是把历史相似题材当作当前题材必然路径。
- 不是用旧题材印象覆盖当日资金事实。
- 不是让日报更长。
- 不是把“观察信号”包装成买入资格。

## Done Definition

第一版实现完成时，必须满足：

- 能从已有日报数据生成 `topic_lifecycle` 结构。
- 能写入 `data/topic-lifecycle/YYYY-MM-DD.json` 和刷新 `index.json`。
- 至少支持三个阶段判断：`观察期`、`主攻期`、`退潮期`。
- 能表达“题材仍可研究，但只能进入淘汰赛复核或历史回看，不能直接进入明日计划”。
- 能把 `realtime_tag_evidence_snapshot` 的采用名称和主攻分支写入题材卡。
- 能把 `decision-ledger` 中极度看好样本关联到所属题材。
- 能把 `candidate-traces` 中淘汰原因回写为题材分歧或失效线索。
- 日报可见输出最多 3 到 5 行，不新增大段论证。
- 有单测覆盖：新题材观察、主攻期确认、退潮期不参与、旧题材过期回看、反证优先压缩题材资格。

## 核心概念

### 题材生命周期卡

题材生命周期卡是某个交易方向在一个交易日的证据快照。它不是概念百科，也不是投资结论。它只回答：

- 今天这个题材处于哪个阶段。
- 这个阶段由哪些事实支持。
- 明天要验证什么。
- 哪些事实出现后不再参与。
- 它和过去样本有什么相似或不同。

### 生命周期阶段

第一版使用受控中文阶段：

| 阶段 | 含义 | 明日处理 |
|---|---|---|
| `观察期` | 有注意力或催化，但资金、扩散、核心承接不足 | 只作观察证据，不进入明日计划 |
| `启动期` | 催化和价格表态初步一致，但扩散仍需确认 | 只提示板块进入淘汰赛复核 |
| `主攻期` | 资金、核心标的、扩散和主线证据共同支持 | 只说明板块可进入淘汰赛复核 |
| `分歧承接期` | 已出现第一次明显分歧，核心和板块仍有承接 | 只让核心进入复核，不扩散后排 |
| `高一致风险期` | 高位一致、后排补涨、追高风险上升 | 只保留核心复核，不追后排扩散 |
| `退潮期` | 资金退、核心弱、反证命中或扩散失败 | 不进入明日复核 |
| `过期回看期` | 当日无新证据，只作为历史经验参考 | 不影响明日动作，只进入复盘样本 |

阶段不是线性必经，也不是固定时长。一个题材可以从 `启动期` 直接失败，也可以在 `分歧承接期` 后重新进入 `主攻期`。

### 复核资格

题材阶段只能影响“是否作为板块证据进入淘汰赛复核”，不能直接生成买入动作、明日标的或个股资格。

受控值：

| 字段值 | 含义 |
|---|---|
| `进入淘汰赛复核` | 题材阶段支持板块进入统一淘汰赛复核 |
| `只让核心进入复核` | 只允许板块锚、核心中军或趋势链核心继续接受后续复核 |
| `只保留核心复核` | 高一致风险下只保留核心样本，后排不进入复核 |
| `只作观察证据` | 不进入明日计划，只进入观察说明 |
| `不进入明日复核` | 题材条件已失效或反证压倒正向证据 |
| `只作历史回看` | 当日无新证据，只留作复盘样本 |

## 数据契约

### `data["topic_lifecycle"]`

日报运行数据中新增可选字段：

```json
{
  "topic_lifecycle": {
    "artifact_version": 1,
    "trade_date": "2026-06-14",
    "cards": [
      {
        "topic_id": "topic-ai-pcb-electronic-materials",
        "topic_name": "PCB电子材料",
        "adopted_label": "PCB电子材料",
        "parent_theme": "AI算力基础设施",
        "aliases": ["PCB", "电子材料", "AI服务器PCB"],
        "lifecycle_phase": "分歧承接期",
        "participation_qualification": "只让核心进入复核",
        "phase_age_trade_days": 3,
        "first_seen_trade_date": "2026-06-10",
        "latest_seen_trade_date": "2026-06-14",
        "evidence_level": "B",
        "evidence": {
          "launch_catalyst": ["AI服务器PCB价值量提升"],
          "fund_attack": ["概念资金净流入", "核心票成交额放大"],
          "core_stocks": [
            {"code": "300476", "name": "胜宏科技", "role": "趋势核心"}
          ],
          "spread_evidence": ["同分支多只个股上涨"],
          "divergence_evidence": ["后排冲高回落"],
          "acceptance_evidence": ["核心票回撤后承接未破"],
          "counter_evidence": ["高位一致后后排亏钱效应上升"]
        },
        "tomorrow_validation": {
          "watch_points": ["核心票是否继续强于后排", "分支成交额是否维持"],
          "upgrade_condition": "核心票继续承接，后排不扩大亏钱效应",
          "downgrade_condition": "核心票失去承接或分支资金明显撤出",
          "invalidation": "核心票破位且板块资金退潮"
        },
        "report_effect": {
          "candidate_policy": "只让核心进入复核，不扩散后排",
          "summary": "PCB电子材料处于分歧承接期，明日只看核心承接，不从后排补涨里找机会。",
          "boundary": "题材阶段只作板块证据，不直接生成明日标的或个股资格。",
          "report_slots": ["板块资金扩散", "淘汰赛复核", "知识复利提示"]
        },
        "source_refs": [
          {"type": "tag_snapshot", "path": "data.realtime_tag_evidence_snapshot"},
          {"type": "decision_ledger", "path": "data/decision-ledger/2026-06-14.json"},
          {"type": "candidate_trace", "path": "data/candidate-traces/2026-06-14.json"}
        ]
      }
    ]
  }
}
```

### Artifact 文件

`data/topic-lifecycle/YYYY-MM-DD.json`：

```json
{
  "artifact_version": 1,
  "trade_date": "2026-06-14",
  "generated_at": "2026-06-14T20:30:00+08:00",
  "source_report": {
    "path": "reports/2026-06-14_A股日报_完整版.md",
    "variant": "full"
  },
  "cards": []
}
```

`data/topic-lifecycle/index.json`：

```json
{
  "artifact_version": 1,
  "latest_trade_date": "2026-06-14",
  "available_trade_dates": ["2026-06-14"],
  "active_topics": [
    {
      "topic_id": "topic-ai-pcb-electronic-materials",
      "topic_name": "PCB电子材料",
      "latest_phase": "分歧承接期",
      "participation_qualification": "只让核心进入复核",
      "latest_trade_date": "2026-06-14",
      "snapshot_path": "data/topic-lifecycle/2026-06-14.json"
    }
  ],
  "by_topic_id": {
    "topic-ai-pcb-electronic-materials": [
      {
        "trade_date": "2026-06-14",
        "phase": "分歧承接期",
        "participation_qualification": "只让核心进入复核",
        "snapshot_path": "data/topic-lifecycle/2026-06-14.json"
      }
    ]
  }
}
```

## 函数签名建议

第一版建议新增纯函数模块：

```text
scripts/knowledge/topic_lifecycle.py
```

建议签名：

```python
def build_topic_lifecycle_snapshot(
    data: dict,
    *,
    previous_index: dict | None = None,
) -> dict:
    ...

def write_topic_lifecycle_artifact(
    snapshot: dict,
    *,
    root_dir: str | Path = ".",
) -> dict:
    ...

def format_topic_lifecycle_for_report(snapshot: dict) -> list[str]:
    ...
```

返回约束：

- `build_topic_lifecycle_snapshot` 不读写文件，只做结构构建。
- `write_topic_lifecycle_artifact` 只写 `data/topic-lifecycle/`。
- `format_topic_lifecycle_for_report` 只输出短句，不做二次判断。
- 所有函数必须能在 Python 3.14 下运行。

## 输入来源

第一版只读取已有数据包和本地 artifact：

| 来源 | 用途 |
|---|---|
| `data["realtime_tag_evidence_snapshot"]` | 题材采用名称、主攻分支、未采用名称、反证信息 |
| `data["market_research_snapshot"]` | 主线、资金、扩散、核心承接 |
| `data["mainline_turnover_summary"]` | 成交额占比和主线容量证据 |
| `data/decision-ledger/index.json` | 题材关联的历史极度看好样本 |
| `data/candidate-traces/YYYY-MM-DD.json` | 候选淘汰、保留、降级原因 |
| `reports/replay/*` | replay 后补验证和失效样本 |
| `wiki/` | 只取稳定规则和来源路由，不直接取当天事实 |

## 阶段判断规则

### 观察期

满足任一条件即可进入：

- 有热榜或社区注意力，但资金证据不足。
- 有新催化，但核心标的未表态。
- 有行业标签，但主攻分支不清楚。

日报动作：

- `participation_qualification = "只作观察证据"`。
- 不进入明日计划。
- 可进入知识复利提示的候选样本。

### 启动期

需要同时具备：

- 明确启动催化或主攻分支。
- 至少一个核心标的价格表态。
- 板块内有初步扩散或资金证据。

日报动作：

- 可以进入淘汰赛复核。
- 只有个股结构、价格行为、账户边界和时间窗口继续满足时，才可能进入最终动作。

### 主攻期

需要同时具备：

- 主线或分支资金证据成立。
- 核心标的承接强于后排。
- 扩散不是单票孤立。
- 没有命中关键反证。

日报动作：

- `participation_qualification = "进入淘汰赛复核"`。
- 复核仍必须经过资金载体、价格行为、反方证据、账户边界和时间窗口。

### 分歧承接期

需要同时具备：

- 已出现冲高回落、后排掉队、核心分歧或板块内部分化。
- 核心标的或中军仍有承接。
- 主攻分支尚未被反证或完全退潮。

日报动作：

- `participation_qualification = "只让核心进入复核"`。
- 不从后排补涨、低辨识度股、纯标签股里找机会。

### 高一致风险期

触发条件：

- 高位连续一致。
- 后排补涨扩散但质量下降。
- 热度强于价格承接。
- 反复出现高开回落或封板质量变差。

日报动作：

- 允许保留核心预案，但不追高扩散。
- 报告必须写明失效条件。

### 退潮期

满足任一条件即可进入：

- 核心标的失去承接。
- 分支资金明显撤出。
- 反证命中当前上涨发动机。
- 候选大面积由可做转为不做。
- 题材只剩旧印象，没有当日资金证据。

日报动作：

- `participation_qualification = "不进入明日复核"`。
- 不进入明日计划。
- 只作为复盘样本和历史对照。

### 过期回看期

触发条件：

- 题材在历史中存在，但当日没有新证据。
- 只在类比或复盘时被引用。

日报动作：

- 不影响明日动作。
- 只允许在知识复利提示或复盘中出现。

## 日报集成

### 市场结构判断

可加入一行压缩判断：

```text
- 题材生命周期：PCB电子材料处于分歧承接期，明日只看核心承接，不从后排补涨里找机会。
```

### 淘汰赛复核

题材进入淘汰赛复核时，必须能回答：

- 所属题材阶段是什么。
- 该阶段是否只作观察、只让核心进入复核，还是允许板块进入复核。
- 候选是核心、中军、补位，还是后排噪音。
- 题材失效时是否会直接取消该候选。

### 知识复利提示

只有出现可复用题材阶段样本时输出：

```text
- 新增样本：PCB电子材料从主攻期进入分歧承接期，核心承接仍在但后排补涨质量下降。
- 下次影响：类似题材第一次分歧时，只让核心进入淘汰赛复核，不从后排补涨中找明日主对象。
```

## Validation & Error Matrix

| 条件 | 处理 |
|---|---|
| 缺少 `trade_date` | 返回错误，不能写 artifact |
| 缺少 tag 快照和主线证据 | 不生成题材卡；日报不输出生命周期判断 |
| 题材只有名称、没有证据 | 不生成题材卡 |
| 题材有反证命中当前上涨发动机 | 阶段不得高于 `退潮期` 或 `只作观察证据` |
| 历史题材当日无新证据 | 只能进入 `过期回看期` |
| 生命周期判断与候选动作冲突 | 候选动作向更谨慎一侧收敛 |
| artifact 写入失败 | 日报可以保留，但运行日志必须写清生命周期 artifact 未落盘 |

## Good / Base / Bad Cases

### Good Case：题材分歧后核心承接

事实：

- 题材前三日资金连续表态。
- 当日后排掉队，但核心标的没有破坏。
- 资金仍集中在主攻分支。

期望：

- 阶段为 `分歧承接期`。
- 复核资格为 `只让核心进入复核`。
- 明日计划只允许核心或中军继续比较。
- 知识复利提示记录“第一次分歧只让核心进入复核”。

### Base Case：新题材只有热度

事实：

- 热榜出现新概念。
- 没有板块资金和核心价格承接。

期望：

- 阶段为 `观察期`。
- 复核资格为 `只作观察证据`。
- 不进入明日计划。

### Bad Case：旧题材凭印象继续可做

事实：

- 题材历史很强。
- 当日没有新资金证据。
- 核心标的走弱。

错误结果：

- 报告继续写“题材仍强，寻找补涨”。

正确结果：

- 阶段为 `退潮期` 或 `过期回看期`。
- 复核资格为 `不进入明日复核`。
- 报告写“旧题材只作历史对照，不从后排找机会”。

## Wrong vs Correct

### Wrong

```text
机器人题材之前持续 7 天，所以这次 AI PCB 大概也能炒 7 天，明日继续找补涨。
```

问题：

- 把历史样本当固定寿命。
- 没有看当前资金、核心承接和反证。
- 把观察信号包装成买入资格。

### Correct

```text
AI PCB 当前处于分歧承接期：资金仍在主攻分支，但后排补涨质量下降。明日只看核心承接，核心失去承接或分支资金撤出，则该题材不进入明日计划。
```

优点：

- 用当前证据判断阶段。
- 明确下一步验证。
- 明确不参与条件。

## 测试要求

新增或扩展测试：

| 测试 | 断言 |
|---|---|
| `tests/test_topic_lifecycle.py` | 构建题材卡、字段完整、阶段判断、artifact 写入 |
| `tests/test_realtime_tag_evidence_snapshot.py` | tag 快照中的采用名称能进入题材卡 |
| `tests/test_decision_ledger.py` | 极度看好样本能关联到题材卡 |
| `tests/test_candidate_trace_artifacts.py` | 淘汰原因能成为分歧或失效线索 |
| `tests/test_daily_report_render.py` | 日报只输出短生命周期判断，不生成辩论长文 |
| `tests/test_llm_wiki_context.py` | LLM Wiki compact context 说明题材生命周期只作证据层，不替代买入资格 |

所有测试使用：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_topic_lifecycle
```

## 实施顺序

1. 新增 `scripts/knowledge/topic_lifecycle.py` 的纯函数和单测。
2. 从 `realtime_tag_evidence_snapshot` 生成第一版题材卡。
3. 接入 `decision-ledger` 和 `candidate-traces`，补充核心样本和淘汰线索。
4. 写入 `data/topic-lifecycle/` artifact 和 index。
5. 在日报市场结构判断或知识复利提示中输出 3 到 5 行压缩结论。
6. 复盘 replay 时允许补充验证结果，但不覆盖原始当日判断。
7. 样本稳定后，再决定是否把复用规则写入 `wiki/板块补充/板块中枢与主线延续.md`。

## 与 LLM Wiki 的关系

题材生命周期 artifact 是运行事实，不是长期知识。只有经过多个样本验证后的规则，才进入 LLM Wiki。

写入建议：

- 单日题材阶段：留在 `data/topic-lifecycle/`。
- 多次出现的阶段规律：进入 `知识复利提示`。
- 经过复盘确认的可复用规则：写入 `wiki/板块补充/板块中枢与主线延续.md`。
- 具体股票买点和参与预案：仍由 `decision-ledger` 承接。

核心边界：LLM Wiki 保存可复用规则，topic lifecycle 保存当日证据过程，日报只消费对明日动作有用的压缩结论。
