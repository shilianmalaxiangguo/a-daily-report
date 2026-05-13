# Daily Report Decision Context

This context names the domain concepts used by the daily-report engine and snap-ui review cockpit. It exists to keep trading judgment, report language, and feedback tracking from drifting into generic stock-list or prediction wording.

## Language

**判断样本**:
A stock case selected by the report because it carries a concrete judgment hypothesis that must be reviewed against later market behavior.
_Avoid_: 普通观察票, 行情记录, 预测对象

**三层假设**:
The required hypothesis bundle for a judgment sample: stock setup, sector candidate, and the market path that would validate the sample.
_Avoid_: 单票评分, 脱离板块的个股判断

**极度看好名单**:
The smallest set of judgment samples the report most strongly wants to track in the current cycle.
_Avoid_: 全量观察池, 必买名单, 确定性答案

**市场演变分支**:
A plausible market path that explains why different prepared samples may be selected by funds under different future conditions.
_Avoid_: 确定预测, 单一路径

**板块关系状态**:
The relationship between candidate sectors during a cycle, such as replacement, inheritance, mixed relay, or alternating competition.
_Avoid_: 单一主线切换, 简单胜负

**趋势命运**:
The observed 25-trading-day path of a judgment sample, including whether it stair-stepped higher, failed directly, shook out before rising, or was wrongly removed.
_Avoid_: 单日涨跌, 简单胜负

**周期复盘验收**:
The end-of-cycle acceptance standard that classifies a judgment sample's 25-trading-day outcome into a controlled conclusion.
_Avoid_: 随口复盘, 只看涨跌

**本地判断账本**:
A testable local artifact produced by the daily-report flow before any Cloudflare D1 synchronization.
_Avoid_: 直接线上写入, 不可重跑数据

**判断账本路径**:
The canonical machine-readable artifact location for local judgment ledger files: `data/decision-ledger/`.
_Avoid_: reports, snap-ui/public/data

**判断账本快照**:
A per-trade-date judgment ledger artifact that records the decision samples and states generated for that report date.
_Avoid_: 巨大总账, 不可审计追加文件

**判断账本索引**:
The manifest for local judgment ledger snapshots, used to find latest dates, stock cycles, and export candidates.
_Avoid_: 手工找文件, 前端硬编码日期

**股票周期索引**:
The stock-code lookup inside the judgment ledger index, used to find all decision cycles and mentions for one stock.
_Avoid_: 只能按日期浏览, 丢失重复点名历史

**真正失败**:
A judgment-sample failure confirmed only when the sector path stops being selected and the stock's own structure or acceptance also breaks.
_Avoid_: 当日没涨, 所属板块当天没被选中

**等待市场选择**:
A judgment-sample state where the stock setup remains intact but its sector path has not yet been selected by market funds.
_Avoid_: 失败, 成功, 当日无效

**市场选择确认**:
A judgment-sample state where the sector path is selected by market funds and the stock's own acceptance or strength follows.
_Avoid_: 个股单独上涨, 板块单独上涨

**确认证据**:
The dated evidence that moved a judgment sample from waiting for market selection into market selection confirmation.
_Avoid_: 事后感觉, 无日期结论

**迭代修正**:
A fieldized rule adjustment derived from mismatch between the original judgment and the sample's later trend fate.
_Avoid_: 读后感, 玄学解释

## Relationships

- An **极度看好名单** contains one or more **判断样本**.
- A **判断样本** must carry one **三层假设** before it can enter cycle tracking.
- A **判断样本** can be mentioned by multiple daily reports during the same 25-trading-day cycle.
- A **判断样本** is evaluated through one **趋势命运** for each cycle.
- A **趋势命运** must end with one **周期复盘验收** conclusion.
- A **趋势命运** may produce one or more **迭代修正** entries.
- A **本地判断账本** is produced and tested before D1 receives synchronized decision records.
- A **判断账本路径** keeps source artifacts in `data/decision-ledger/` before snap-ui export.
- A **判断账本路径** contains one **判断账本索引** and many **判断账本快照** files.
- A **判断账本快照** is keyed by report trade date.
- A **判断账本索引** exposes latest trade date, available trade dates, and one **股票周期索引**.
- A **市场演变分支** explains why a **判断样本** may become active, remain pending, or be removed.
- A **板块关系状态** explains whether a sector was replaced, inherited the prior line, entered mixed relay, or alternated with another candidate sector.
- A **真正失败** requires both sector-path rejection and stock-level structure or acceptance failure.
- **等待市场选择** applies when the sector path is not selected yet but the stock setup remains intact.
- **市场选择确认** requires both sector-level selection and stock-level acceptance or strength.
- **确认证据** belongs to one **市场选择确认** and must include the confirmation date plus sector and stock evidence.

## Example Dialogue

> **Dev:** "If three stocks all look good, should D1 mark all three as winners or losers tomorrow?"
> **Domain expert:** "No. They are **判断样本**. Each one belongs to a possible **市场演变分支**; the review should record which branch the market selected and whether our sample removal or retention logic was right."

> **Dev:** "Can we rank the stock only by its K-line setup?"
> **Domain expert:** "No. A **判断样本** needs a **三层假设**: the stock setup, the sector it depends on, and the market path that would make that sector active."

## Flagged Ambiguities

- "观察池" can mean either a broad stock list or a report-owned judgment surface. Resolved: use **极度看好名单** for the high-conviction subset and **判断样本** for cycle-tracked cases.
- "看好" must not imply certainty or direct buying. Resolved: it means the sample is worth tracking under explicit conditions and future market selection.
- "个股好" must not be evaluated away from market and sector context. Resolved: every cycle-tracked **判断样本** must include the **三层假设**.
- "板块切换" must not imply a clean one-step handoff. Resolved: record the **板块关系状态**, including mixed relay and alternating competition.
- "失败" must not mean a stock failed to rise on one day. Resolved: during mixed relay, only call **真正失败** when sector selection and stock evidence both deteriorate.
- "未验证" must not be treated as failure. Resolved: use **等待市场选择** when the stock setup remains intact and the sector path has not yet been chosen.
- "被市场选择" must not mean a stock rose alone or a sector rose alone. Resolved: use **市场选择确认** only when sector and stock evidence confirm together.
- "确认" must not be a timeless label. Resolved: every **市场选择确认** needs dated **确认证据**.
- "复盘" must not be uncontrolled commentary. Resolved: every 25-trading-day cycle ends with one **周期复盘验收** conclusion.
- "D1" must not be the first write target for new decision logic. Resolved: produce a testable **本地判断账本** first, then synchronize to D1 after validation.
- "判断账本" must not be mixed with human-readable reports or frontend publish artifacts. Resolved: source files live under **判断账本路径**.
- "总账" must not begin as one ever-growing file. Resolved: use daily **判断账本快照** files plus one **判断账本索引**.
- "索引" must not only mean latest date. Resolved: include **股票周期索引** so snap-ui can inspect one stock across reports and cycles.
