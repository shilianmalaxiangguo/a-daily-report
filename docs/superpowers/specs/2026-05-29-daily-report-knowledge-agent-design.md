# Daily Report Knowledge Agent Design

## Goal

把外部三个知识类 skill 的可取之处吸收到本仓库，形成一套适合 A 股日报的经验库前置判断系统。目标不是多放一个知识展示区，而是让 `wiki/` 中已经沉淀的交易体系在日报生成、复盘、问股和报告修正前先被命中、压缩、引用，再进入具体判断。

## In Scope

- 梳理 `knowledge-ops`、`knowledge-agent`、`llm-wiki` 三个外部 skill 中可借鉴的结构。
- 设计本仓库的经验库前置判断链路：事实提取、主题路由、经验命中、报告体现、复盘回写。
- 定义 `knowledge_hits` 数据契约，让日报能说明本次判断引用了哪些经验。
- 设计一个后续可创建的 Codex skill：`daily-report-knowledge-anchor`，用于约束 agent 在交易判断前先读取经验库。
- 明确第一阶段不用向量数据库，先使用可解释的主题索引和命中证据；保留后续混合检索升级路径。

## Out Of Scope

- 不在本 spec 中实现代码。
- 不创建新的 skill 文件。
- 不重写现有 `wiki/` 目录结构。
- 不引入向量数据库、外部服务或新依赖。
- 不让经验库替代实时行情、公告、盘口、成交和账户事实。

## Non Goals

- 不把 Wiki 变成聊天记录仓库。
- 不自动把 AI 推断写成正式交易经验。
- 不让检索结果直接改变交易动作；命中的经验只提供判断前提和解释依据，动作仍要由事实、账户约束和既有报告链路共同决定。
- 不复制外部 skill 的实现文本或目录结构，只吸收适合本仓库的设计模式。

## External Nutrients

| 外部来源 | 可取之处 | 本仓库吸收方式 | 不照搬的部分 |
| --- | --- | --- | --- |
| `knowledge-ops` | 多层知识系统；支持保存、整理、同步、去重、检索；强调 frontmatter、索引、摘要、去重和唯一归属。 | 作为经验库维护规范：新知识先找唯一归属节点，更新索引，保留来源，做重复检查。 | 不照搬跨系统同步、MCP memory、Supabase、Git repo 多后端复杂度。 |
| `knowledge-agent` | focused corpus / custom brain；先 build corpus，再 prime，最后 query；新观察进入后 rebuild/reprime。 | 将日报经验拆成多个 focused prior：市场结构、候选质量、账户执行、盘中问股、知识复利。日报生成前按当天事实选择并加载相关 prior。 | 不以 claude-mem observations 为主数据源；本仓库权威经验源仍是 `wiki/`。 |
| `llm-wiki` | raw sources -> wiki -> schema 三层；Wiki 是 compiled artifact，不是每次临时重推导；页面带来源、标签、关系和生命周期。 | 建立本仓库的经验库 schema：每条经验有来源、主题、适用事实、可信度、关系、报告落点。 | 不强制迁移到 Obsidian，不要求所有页面马上改成完整 YAML frontmatter。 |

Sources:

- https://www.skills.sh/affaan-m/everything-claude-code/knowledge-ops
- https://www.skills.sh/thedotmack/claude-mem/knowledge-agent
- https://www.skills.sh/ar9av/obsidian-wiki/llm-wiki

## Current Problem

现在 `scripts/knowledge/llm_wiki_context.py` 已经把 Wiki 中的规则压缩成 `source_paths`、`field_mappings`、`report_digest_text` 等字段，日报生成时也会把它注入到 `data["knowledge"]["llm_wiki"]`。这说明 Wiki 不是纯摆设。

但当前缺口是：日报生成没有一个明确的“当天事实 -> 命中经验 -> 影响判断 -> 报告呈现”的闭环。很多经验已经在 compact context 里，但日报并不知道今天为什么该用哪几条，也很难解释“这次判断参考了哪些经验”。这会让经验库看起来像挂件，而不是判断前提。

## Proposed Architecture

### 1. Knowledge Schema

先不大规模修改所有 Wiki 页面。第一阶段新增一个运行索引层，把已有 Wiki 规则编译成可命中的结构化条目。

建议条目字段：

```json
{
  "id": "account.unbuyable-core-anchor",
  "source_path": "wiki/交易思想/实际账户情况.md",
  "title": "实际不可买不降低市场身份",
  "topics": ["账户", "实际可买", "持仓", "候选比较"],
  "trigger_facts": ["账户本金不足", "一手金额过高", "688开头", "实际不可买"],
  "applies_to": ["daily_report", "intraday_question", "candidate_quality"],
  "confidence": "verified",
  "lifecycle": "active",
  "relationships": [
    {"type": "uses", "target": "candidate.quality-action-layer"},
    {"type": "constrains", "target": "position.sizing"}
  ],
  "report_slots": ["经验库命中", "候选质量", "账户约束"],
  "decision_effect": "只影响账户是否参与，不降低市场身份或板块锚价值"
}
```

字段含义：

| 字段 | 用途 |
| --- | --- |
| `id` | 稳定识别一条经验。 |
| `source_path` | 指向权威 Wiki 节点。 |
| `topics` | 用于主题路由。 |
| `trigger_facts` | 当天事实命中条件。 |
| `applies_to` | 适用场景。 |
| `confidence` | `draft`、`reviewed`、`verified`、`disputed`、`archived`。 |
| `relationships` | 经验之间的关系。 |
| `report_slots` | 命中后应进入日报哪个版面。 |
| `decision_effect` | 本次最多影响什么，避免无限外溢。 |

### 2. Focused Priors

借鉴 `knowledge-agent`，把经验库拆成 focused prior，而不是每次加载整个 Wiki。

第一阶段建议五组：

| Prior | 覆盖范围 | 典型来源 |
| --- | --- | --- |
| `market-structure-prior` | 指数、赚钱效应、成交扩散、主线延续、题材新鲜度。 | `wiki/板块补充/板块中枢与主线延续.md`、`wiki/交易思想/AI摩擦与知识复利.md` |
| `candidate-quality-prior` | 候选评分、动作层级、风险项、恢复条件、取关条件。 | `wiki/交易思想/扣分系统与动作分层.md` |
| `account-execution-prior` | 1w 账户、一手约束、实际可买/不可买、仓位表达。 | `wiki/交易思想/实际账户情况.md` |
| `intraday-question-prior` | 做T、点位依据、VWAP、MA、时间窗口、盘中问股继承。 | `wiki/交易思想/做T与风险控制.md`、`wiki/交易思想/价格行为与能量框架.md` |
| `knowledge-compounding-prior` | 判断样本、错题、AI 摩擦、复盘回写、经验沉淀。 | `wiki/交易思想/判断样本与市场演变.md`、`wiki/交易思想/AI摩擦与知识复利.md` |

日报生成前先根据当天事实选择 prior，再产出命中结果。这样经验库是判断前提，不是事后附录。

### 3. Knowledge Hits

新增 `knowledge_hits` 作为日报和诊断的共同证据层。

建议数据结构：

```json
{
  "knowledge_hits": [
    {
      "hit_id": "kh-001",
      "knowledge_id": "market.index-strong-breadth-weak",
      "source_path": "wiki/板块补充/板块中枢与主线延续.md",
      "triggered_by": ["指数上涨", "上涨家数偏弱", "成交集中"],
      "matched_topics": ["市场结构", "低频聚焦"],
      "impact": "指数强但赚钱效应弱时，只保留主线核心，不从旧方向强行扩散候选",
      "report_slot": "市场结构判断",
      "confidence": "verified"
    }
  ]
}
```

报告中只显示短表：

| 命中经验 | 触发事实 | 本次影响 | 来源 |
| --- | --- | --- | --- |
| 指数强但赚钱效应弱 | 指数上涨但上涨家数偏弱 | 只保留主线核心，不扩散旧方向 | 板块中枢与主线延续 |

### 4. Daily Report Knowledge Anchor Skill

后续可创建一个个人 skill，名字建议 `daily-report-knowledge-anchor`。

触发场景：

- 用户要求生成日报、复盘日报、修报告口径。
- 用户问某只股票、某个板块、某次交易是否该做。
- 用户要求把经验写入 Wiki。
- 用户担心判断漂移、前后矛盾、经验库没有体现。

Skill 核心步骤：

1. 识别当前问题域。
2. 读取 `wiki/README.md` 的路由。
3. 读取相关 Wiki 节点或索引条目。
4. 列出“本次判断前提”。
5. 再做交易判断、报告修正或代码修改。
6. 若发现 Wiki 缺口，输出建议沉淀节点，不自动写入正式经验。

这层解决 agent 自己不飘。仓库里的 `knowledge_hits` 解决日报生成不飘。

## Daily Generation Flow

```text
输入事实
  -> 提取主题
  -> 选择 focused prior
  -> 命中经验条目
  -> 生成 knowledge_hits
  -> 报告判断读取 knowledge_hits
  -> 日报短表展示命中经验
  -> 复盘时比较命中经验与实际结果
```

输入事实来自现有日报数据，不新增外部事实源：

- 市场状态：指数、上涨家数、跌停、成交额、主线强弱。
- 板块状态：成交占比、扩散、核心承接、中军反馈。
- 候选状态：身份、板块、风险、形态、成本、买点质量。
- 账户状态：本金、一手金额、可买、不可买、已有持仓。
- 复盘状态：当时判断、实际走势、偏差原因。

## Retrieval Strategy

第一阶段使用可解释检索：

1. 主题和关键词路由。
2. Wiki 节点索引。
3. `field_mappings` 精确匹配。
4. 报告场景过滤。
5. 可信度和生命周期过滤。

第二阶段再考虑轻量全文检索。

第三阶段才考虑向量数据库或混合检索。向量检索只能用于召回候选经验，不能直接决定报告结论。最终命中仍要落到可解释的 `knowledge_id`、`source_path` 和 `impact`。

## Maintenance Flow

借鉴 `knowledge-ops` 和 `llm-wiki`，新经验进入系统时按下面顺序处理：

1. 先查是否已有归属节点，避免重复造页。
2. 若是文章或盘中经验，先提炼成字段化规则。
3. 写入最贴近的 Wiki 节点。
4. 更新运行索引或 compact context。
5. 增加测试，证明经验能被命中或被报告引用。
6. 若只是 AI 推断，标记为 `draft` 或 `reviewed`，不直接改变交易动作。
7. 复盘后再决定是否升为 `verified`。

## Acceptance Examples

### Example 1: 指数强但赚钱效应弱

事实：

- 指数上涨。
- 上涨家数偏弱。
- 成交集中在少数方向。

期望：

- 命中 `market-structure-prior`。
- 命中来源指向 `wiki/板块补充/板块中枢与主线延续.md`。
- 报告输出：只保留主线核心，不从旧方向强行扩散候选。

### Example 2: 账户实际不可买

事实：

- 候选是市场核心。
- 一手金额超过账户可承受范围。

期望：

- 命中 `account-execution-prior`。
- 报告区分市场身份和账户动作。
- 输出：不可买只影响当前账户参与，不降低市场核心或板块锚价值。

### Example 3: 新股周期判断

事实：

- 当天有新股或次新情绪出口。
- 市场处于弱修复或强修复阶段。

期望：

- 命中 `wiki/交易思想/新股周期与市场情绪.md`。
- 报告不把历史相似样本当作当前买点。
- 输出：新股情绪只作为周期和承接判断，仍要回到单票承接验证。

### Example 4: 做T问股

事实：

- 用户盘中问是否做T。
- 标的处于亏损或反弹阶段。

期望：

- 命中 `intraday-question-prior`。
- 输出先看防守线、止盈线、买回确认。
- 不把“更便宜”当作更正确。

## Testing Plan

- `tests/test_llm_wiki_router.py`
  - 给定事实标签，断言命中正确 knowledge 条目。
  - 断言命中结果包含 `source_path`、`triggered_by`、`impact`。

- `tests/test_llm_wiki_context.py`
  - 继续保护 compact context。
  - 增加索引字段或 focused prior 的存在性断言。

- `tests/test_use_report_sections.py`
  - 断言报告能渲染“经验库命中”短表。
  - 断言没有命中时不输出空表。

- `tests/test_report_runtime.py`
  - 断言日报运行数据包含 `knowledge_hits`。
  - 断言 `knowledge_hits` 不替代实时事实。

## Done Definition

- 有一份结构化经验索引设计。
- 有 focused prior 划分。
- 有 `knowledge_hits` 数据契约。
- 有日报生成链路中的使用位置。
- 有后续 skill 的职责边界。
- 有测试计划证明经验库能进入报告判断前提。

## First Implementation Slice

第一片只做最小闭环：

1. 新增 `scripts/knowledge/llm_wiki_router.py`。
2. 从现有 `FIELD_MAPPINGS` 中手工登记 8 到 12 条高价值经验。
3. 根据输入事实命中 1 到 3 条经验。
4. 在报告知识模块渲染“经验库命中”短表。
5. 增加三类测试：市场结构、账户约束、做T问股。

不做：

- 不上向量库。
- 不改全部 Wiki frontmatter。
- 不重写日报主链。
- 不自动把命中经验改成交易动作。

## Open Questions

- `knowledge_hits` 是否默认进入正式日报，还是先只进入 replay/诊断输出？
- 经验条目的索引第一阶段放在 Python 常量里，还是放在 `wiki/运行契约/经验库索引.md`？
- `daily-report-knowledge-anchor` skill 是先作为本仓库 skill，还是安装到个人 Codex skills 目录？
