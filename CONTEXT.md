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

**趋势比价链**:
The relative-price chain that explains how a trend theme prices high-position anchors, middle transmitters, and low-position catch-up stocks during one market phase.
_Avoid_: 单票故事, 只看新闻逻辑, 孤立形态判断

**阶段价差**:
The tradable price gap created when funds compare high-position anchors with lower-position names in the same or adjacent trend chain.
_Avoid_: 便宜就买, 低位等于安全, 高位等于不能参与

**参与窗口**:
The concrete next-day participation timing attached to a judgment sample, such as auction participation, first-minutes attack, reseal participation, board participation, or no participation.
_Avoid_: 一直观察, 笼统等确认, 看好后无动作

**预演情境**:
The designed next-day scenario set prepared after today's report, covering what conditions would justify participation, cancellation, or an alternative action.
_Avoid_: 临盘瞎蒙, 看好后随机应变, 单一路径预测

**参与预演复盘**:
The replay-quality result that compares a stored participation rehearsal with next-day facts.
_Avoid_: 事后长评, 感觉对了, 感觉错了

**竞价表态**:
The pre-open signal where meaningful funds express intent through auction price, matched volume, order stability after 09:20, and sector synchronization.
_Avoid_: 竞价高开就买, 散户情绪猜测, 无量高开

**回封参与**:
The participation window after a limit-up stock opens, absorbs selling pressure, and quickly reseals with improving order quality and sector support.
_Avoid_: 炸板就买, 多次弱回封, 孤立回封

**错过后动作**:
The planned response when the primary target becomes too fast, too high, or unavailable, usually shifting from the high-position anchor to a lower-position relative-price candidate or skipping the phase.
_Avoid_: 追高补票, 临时换杂毛, 错过后情绪化补偿

**进攻仓位三态**:
The position model that replaces legacy conservative sizing: 0% when there is no tradable target or the market is at ice point, 50% for a valid attack target, and 100% for the clear core target.
_Avoid_: 用缩仓替代判断, 看好却没有参与脚本, 风险条件不清

**市场演变分支**:
A plausible market path that explains why different prepared samples may be selected by funds under different future conditions.
_Avoid_: 确定预测, 单一路径

**主攻线**:
The same-day sector line receiving the clearest fund attack through net inflow, high-position strength, broad sector gains, strong gain clusters, or batch limit-ups.
_Avoid_: 明日保证方向, 单一新闻题材, 只有口号没有资金态度

**主线确认**:
The judgment that a **主攻线** has enough same-day fund-attack evidence to be named directly before judging relationships or stages.
_Avoid_: 把确认拖到趋势末端, 用阶段复核替代资金态度, 复杂化简单主线

**主线攻击证据**:
The fieldized evidence package used before **主线确认**, describing whether funds actually attacked a sector through net inflow, limit-up breadth, high-position anchors, broad rally, strong gain clusters, or turnover-share expansion.
_Avoid_: 新闻热度, 口号主线, 单票孤立上涨, 不可复核的主观判断

**主线容量**:
The liquidity capacity estimate for how many simultaneous market lines current turnover can realistically support, judged by yesterday comparison and the recent 25-trading-day turnover baseline.
_Avoid_: 永久固定阈值, 经验锚点前台化, 用成交额替代资金进攻方向, 低容量硬找多主线

**主线格局**:
The market-level classification of whether current funds show no line, one focused line, two competing lines, a main line plus background line, chaotic relay, or bull-market multi-line behavior.
_Avoid_: 非牛市三主线, 把电风扇轮动当多主线, 每个热点都叫主线

**板块关系状态**:
The relationship between candidate sectors during a cycle, such as replacement, inheritance, mixed relay, or alternating competition.
_Avoid_: 单一主线切换, 简单胜负

**主线进程**:
The stage of an already identified market line after funds have shown an attack attitude through inflow, high-position strength, broad sector gains, or batch limit-ups.
_Avoid_: 把主线确认复杂化, 把阶段判断当成主线初因, 主线口号

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
A per-trade-date judgment ledger artifact that records the decision samples, states, and planned participation generated for that report date.
_Avoid_: 巨大总账, 不可审计追加文件, 只存Markdown不存预演方案

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
- An **极度看好名单** must not stop at tracking; each high-conviction **判断样本** needs a **参与窗口** or an explicit **错过后动作**.
- A **判断样本** must carry one **三层假设** before it can enter cycle tracking.
- A core **判断样本** needs at least one **预演情境** for participation, cancellation, and missed-entry handling before it can guide next-day action.
- A **判断样本** in a trend-driven phase should be placed on one **趋势比价链** when the sector has high-position anchors, middle transmitters, or low-position catch-up candidates.
- A **趋势比价链** can create one or more **阶段价差** opportunities, but only if the relevant **参与窗口** and risk boundary are explicit.
- A **参与窗口** must choose one **进攻仓位三态** state: 0%, 50%, or 100%; old 30% trial sizing is legacy and should not guide new reports.
- A **判断样本** can be mentioned by multiple daily reports during the same 25-trading-day cycle.
- A **判断样本** is evaluated through one **趋势命运** for each cycle.
- A **趋势命运** must end with one **周期复盘验收** conclusion.
- A **趋势命运** may produce one or more **迭代修正** entries.
- A **本地判断账本** is produced and tested before D1 receives synchronized decision records.
- A **判断账本路径** keeps source artifacts in `data/decision-ledger/` before snap-ui export.
- A **判断账本路径** contains one **判断账本索引** and many **判断账本快照** files.
- A **判断账本快照** is keyed by report trade date.
- A **判断账本快照** must persist each core sample's **预演情境** as machine-readable `planned_participation`, including participation window, position state, auction, first-minutes, board, reseal, missed-entry, and cancellation.
- `planned_participation` belongs at case-level for the current plan and mention-level for the original report mention, so replay can compare tomorrow's behavior against the designed scenario.
- A **判断账本快照** may persist **参与预演复盘** as machine-readable `participation_review` after next-day facts are available.
- `participation_review` uses fact fields such as `auction_matched`, `first_minutes_accepted`, `board_sealed`, `reseal_success`, `sector_supported`, `cancellation_triggered`, `primary_unavailable`, and `missed_action_worked`.
- **参与预演复盘** must classify the design quality as **预演命中**, **预演作废**, **错过后方案命中**, **预演过早**, or waiting for more facts.
- A **判断账本索引** exposes latest trade date, available trade dates, and one **股票周期索引**.
- A **判断账本索引** carries `participation_review_status` and a compact `participation_review` summary so snap-ui can list **参与预演复盘** quality without loading every snapshot first.
- A **市场演变分支** explains why a **判断样本** may become active, remain pending, or be removed.
- A **主线容量** informs **主线格局** by estimating whether current turnover can support no line, one focused line, two lines, or bull-market multi-line behavior.
- A **主线格局** is judged before **主线确认** so a low-volume rotation market can remain **无主线** instead of forcing a weak **主攻线**.
- **主线攻击证据** is evaluated before **主线确认** and must expose which concrete fund-attack fields were present or absent.
- A **主线确认** names the current **主攻线** from same-day fund-attack evidence before **板块关系状态** and **主线进程** are judged.
- A **板块关系状态** explains whether a **主攻线** replaced, inherited, mixed with, or alternated against another candidate sector.
- A **主线进程** follows mainline identification and describes whether an already selected line is starting, advancing, accelerating, accepting divergence, slowing, or exhausting.
- A **主线进程** can support **市场选择确认**, but it does not replace stock-level acceptance or a concrete **参与窗口**.
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
- "看好后继续观察" must not hide a missing participation strategy. Resolved: high-conviction samples need a **参与窗口** such as **竞价表态**, first-minutes attack, **回封参与**, board participation, or an explicit **错过后动作**.
- "个股好" must not be evaluated away from market and sector context. Resolved: every cycle-tracked **判断样本** must include the **三层假设**.
- "集合竞价强" must not mean automatic buying. Resolved: use **竞价表态** only when price, matched volume, post-09:20 order stability, and sector synchronization support the same conclusion.
- "涨停了" must not be enough to participate. Resolved: **回封参与** requires selling-pressure release, quick reseal, improving order quality, and sector support.
- "错过龙头" must not become emotional chasing. Resolved: use **错过后动作** to decide whether to shift down the **趋势比价链** or skip the phase.
- "早盘不当炮灰" must not mean never participating early. Resolved: early participation is allowed only for trend-chain anchors with clear **竞价表态** plus opening acceptance or quick reseal; without that evidence, keep the defensive wait-and-confirm discipline.
- "极度看好" must not grant an early participation window by itself. Resolved: early participation windows belong only to **趋势比价链** anchors or core transmitters; ordinary high-conviction samples only receive tracking conditions.
- "明日策略" must not be a single prediction. Resolved: use **预演情境** to design multiple next-day paths in advance, including participation, cancellation, and missed-entry handling; execution is valid only when one designed high-quality scenario appears.
- "仓位规划" must not keep the old conservative trial ladder. Resolved: use **进攻仓位三态**; unless there is no target or the market is at ice point, the report should start from 50% and recommend 100% only for the clear core target with explicit invalidation.
- "成交额阈值" must not become a public fixed rule. Resolved: judge **主线容量** from today's turnover versus yesterday and the recent 25-trading-day median; old regime anchors stay out of front-page report language.
- "三条以上热点" must not be treated as **多主线** by default. Resolved: outside a bull or super-bull market, three or more active directions usually means **混沌接力**, rolling rotation, or **无主线** rather than a stable multi-line structure.
- "主线确认" must not wait for perfect continuation evidence. Resolved: if same-day fund attack is clear, name the **主攻线** first; then separately judge **板块关系状态** and **主线进程** for next action.
- "资金进攻" must not stay as a prose claim. Resolved: use **主线攻击证据** fields such as net inflow, limit-up breadth, high-position anchors, broad rally, strong gain clusters, and turnover-share expansion before naming a **主攻线**.
- "板块切换" must not imply a clean one-step handoff. Resolved: record the **板块关系状态**, including mixed relay and alternating competition.
- "当日主线" must not be hard to recognize when funds are clearly attacking one direction. Resolved: identify the line first from fund attack attitude such as net inflow, high-position strength, broad sector gains, strong gain clusters, or batch limit-ups; use **主线进程** only afterward to judge stage and next action.
- "失败" must not mean a stock failed to rise on one day. Resolved: during mixed relay, only call **真正失败** when sector selection and stock evidence both deteriorate.
- "未验证" must not be treated as failure. Resolved: use **等待市场选择** when the stock setup remains intact and the sector path has not yet been chosen.
- "被市场选择" must not mean a stock rose alone or a sector rose alone. Resolved: use **市场选择确认** only when sector and stock evidence confirm together.
- "确认" must not be a timeless label. Resolved: every **市场选择确认** needs dated **确认证据**.
- "复盘" must not be uncontrolled commentary. Resolved: every 25-trading-day cycle ends with one **周期复盘验收** conclusion.
- "D1" must not be the first write target for new decision logic. Resolved: produce a testable **本地判断账本** first, then synchronize to D1 after validation.
- "判断账本" must not be mixed with human-readable reports or frontend publish artifacts. Resolved: source files live under **判断账本路径**.
- "总账" must not begin as one ever-growing file. Resolved: use daily **判断账本快照** files plus one **判断账本索引**.
- "索引" must not only mean latest date. Resolved: include **股票周期索引** so snap-ui can inspect one stock across reports and cycles.
- "参与脚本" must not remain only in Markdown. Resolved: store it as `planned_participation` in **判断账本快照** so later review can compare the designed scenario with the next-day market path.
- "参与预演复盘" must not become free-form hindsight. Resolved: store `participation_review` only from explicit next-day facts and controlled labels such as **预演命中**, **预演作废**, **错过后方案命中**, and **预演过早**.
- "`participation_review` only in daily snapshots" must not hide review quality from snap-ui lists. Resolved: expose `participation_review_status` in **判断账本索引** as the lightweight list field.
