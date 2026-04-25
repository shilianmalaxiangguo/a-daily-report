# A Daily Report XHigh Operating System Design

Date: 2026-04-25
Scope: `a-daily-report` report product, skill workflow, memory extraction, and learning loop
Status: Draft for user review
Baseline: `a1f9780 checkpoint before workflow memory TDD`

## 1. Why This Spec Replaces The Previous One

The previous memory-optimization spec was方向对的，但执行顺序太快：它直接把“记忆提取”落成 runtime、CLI、hook。这个方向容易把问题误解成“加一个记忆数据库”，而不是先回答一个更大的问题：

> 这个日报到底应该怎样像一个交易研究团队一样工作？

所以本 spec 重新从产品和认知流程出发，而不是从代码模块出发。

本轮已经把 `develop` 回到 `a1f9780`。之前那批探索性实现不作为当前主线继续推进，只作为经验：

1. 记忆系统必须有 review artifact，不能静默改正式记忆。
2. 同一来源重复应用不能让候选记忆误晋升。
3. Skill 入口应该是意图路由，不是固定 command 手册。
4. 但这些实现不能先于更深的日报产品定义。

## 2. Core Thesis

`a-daily-report` 不应该只是“生成 Markdown 的脚本”。

它应该是一个小型交易研究操作系统：

1. **盘前作战系统**
   - 2 分钟内回答明天能不能做、看谁、什么时候确认、错了怎么办。

2. **盘中执行参照**
   - 给出 10 点确认、60 分钟买点、30 分钟止损、尾盘例外这些可执行节奏。

3. **盘后复盘系统**
   - 记录当天判断是否被市场验证，哪些对象进入/退出观察。

4. **跨日学习系统**
   - 把重复出现的表达偏好、报告 bug、数据源坑、交易规则修正沉淀下来。

5. **Skill 驱动的自然语言入口**
   - 用户不需要记命令；模型根据意图选择日报生成、修复、复盘、沉淀记忆或优化 skill。

真正要优化的是这五层如何配合，而不是单独多写一个 memory runtime。

## 3. Current Baseline Reading

当前 `a1f9780` 已经包含 V2 日报结构和大量节点化改造。

### 3.1 已经成立的部分

1. 前台已经从“数据堆叠”转向“交易简报”：
   - `交易纪律`
   - `市场基底`
   - `周期与主线`
   - `资金意图`
   - `个股解读`
   - `明日执行计划`
   - `最终结论`

2. 报告已经开始把重数据和连续性放到附录：
   - 历史主线池
   - 主线切换记录
   - 主线成交额占比历史
   - 个股观察生命周期
   - A 杀淘汰记录

3. V2 后续计划里已经识别出几个真实剩余问题：
   - 结构化主线历史还需要 backfill。
   - 主线成交额占比还需要多日连续历史。
   - 60 分钟确认需要用 April 成功/失败案例校准。
   - final focus 不能被 tracking-memory 观察项误覆盖。

### 3.2 尚未成立的部分

1. 缺一个真正的 skill 入口，把用户自然语言映射到工作流。
2. 缺一个“经验沉淀”的机制，把重复修正变成可复用上下文。
3. 缺一个明确的记忆治理规则，防止记忆误晋升、过期规则继续生效。
4. 缺一个报告验收协议，区分：
   - 结构验收
   - 文案验收
   - 数据真实性验收
   - 交易逻辑验收
   - 复盘有效性验收

## 4. User-Facing Product Contract

日报必须先服务用户的真实交易动作。

### 4.1 盘前合同

用户打开报告前台，应能直接回答：

1. 明天总体是 `不做`、`观察`、`条件试错`，还是 `可做`？
2. 当前市场底色是什么？
3. 周期主线是什么？
4. 当天主攻线和周期主线是否一致？
5. 唯一重点对象是谁？如果没有，必须写 `暂无 / 不做`。
6. 10 点附近看什么？
7. 什么情况直接放弃？

### 4.2 盘中合同

日报不应该给模糊鼓励，而应该给执行参照：

1. `09:25-09:40`：只看竞价和风险，不抢。
2. `09:50-10:10`：确认市场底色、主线承接、唯一对象强弱。
3. `10:00左右`：弱仓/错仓处理优先。
4. 买点：必须等主线确认、承接、60 分钟结构。
5. 止损：买后用 30 分钟结构刷新，不机械依赖固定 `-5%`。
6. 尾盘：只作为量化电风扇行情例外，不是常规开仓窗口。

### 4.3 盘后合同

盘后复盘不是解释今天发生了什么，而是更新明天的状态：

1. 哪个主线强化、分化、退潮或接替？
2. 哪些股票继续观察、降级、淘汰？
3. 哪些执行规则被市场验证或打脸？
4. 数据源有没有降级、缺失或误导？
5. 哪些日报表达/结构需要进入工作流记忆？

## 5. Knowledge Architecture

整个系统的知识应该分成五层，不能混在一起。

### 5.1 Structural Specs

保存慢变化结构。

适合放入 spec 的内容：

1. V2 前台顺序。
2. 附录分层。
3. 节点边界。
4. 记忆治理规则。
5. 验收协议。

不适合放入 spec 的内容：

1. 每次用户纠正的表达偏好。
2. 某个数据源当天挂了。
3. 某个 bug 的具体修复路径。
4. 某只股票临时观察结论。

### 5.2 Workflow Memory

保存中速变化的工作经验。

它回答：

1. 用户一再强调的表达偏好是什么？
2. 这个 repo 的真实验收面是什么？
3. 哪类 bug 常出现在哪些文件附近？
4. 哪些旧词、旧规则、旧解释方式应该避免？

Workflow memory 不是 stock memory，也不是 spec。

### 5.3 Market Object Ledgers

保存市场对象连续性。

它回答：

1. 主线什么时候开始、强化、切换、退潮？
2. 个股什么时候进入观察、二次确认、淘汰？
3. A 杀冷却期是否还在？
4. 成交额占比是否连续抬升？

这类信息应该是结构化 runtime atoms，不应该主要解析旧 markdown。

### 5.4 Case Calibration Library

保存交易规则校准样本。

它回答：

1. April 成功样本如何走出来？
2. 失败样本在什么位置该被识别？
3. 固定 `-5%` 会不会误杀？
4. 哪些 stop mode 更贴近真实走势？

这层比 workflow memory 更接近交易模型，应有更严格的数据证据。

### 5.5 Raw Artifacts

保存不可替代的证据表面。

包括：

1. replay markdown。
2. frozen snapshots。
3. generated reports。
4. test output。
5. session summaries。

Raw artifacts 只作为证据来源，不应被当成主要业务状态。

## 6. Memory Governance

记忆系统的核心不是“多记”，而是“别乱信”。

### 6.1 Memory Card Types

最少需要这些类型：

1. `user_preference`
   - 用户稳定偏好。
   - 例：日报先说结论，再说为什么。

2. `report_wording`
   - 报告表达规则。
   - 例：不要解释草稿般的概念。

3. `workflow_lesson`
   - repo 工作方式。
   - 例：报告输出 bug 以 replay markdown 验收。

4. `data_source_lesson`
   - 数据源真实性规则。
   - 例：缺失时显示 `待累计`，不能假装 `0.00%`。

5. `trading_rule`
   - 交易规则修正。
   - 例：市场贴合度只校准视野，不直接给买入资格。

6. `case_calibration`
   - 样本校准结论。
   - 例：某类结构适合 `结构容忍带` 而不是固定止损。

7. `retired_rule`
   - 已退役规则。
   - 例：固定 `-5%` 是唯一止损方式。

### 6.2 Evidence Rules

候选记忆不能因为重复应用同一份 artifact 就晋升。

晋升必须满足至少一种：

1. 两个以上独立来源支持。
2. 用户明确确认。
3. 有 replay/test 作为行为证据。
4. 同一问题在不同日期重复出现。

每条 memory card 应至少记录：

| Field | Meaning |
|-------|---------|
| `id` | 稳定 id |
| `type` | 记忆类型 |
| `summary` | 一句话规则 |
| `details` | 简短细节 |
| `scope` | 适用范围 |
| `confidence` | `candidate / validated / retired` |
| `evidence_sources` | 独立证据来源 |
| `last_seen` | 最近看到日期 |
| `apply_when` | 什么时候用 |
| `do_not_apply_when` | 什么时候不能用 |

### 6.3 Apply Rules

1. 提取阶段只生成 review artifact。
2. 应用阶段才写正式 memory。
3. 默认不自动应用。
4. 同一来源重复应用只刷新 `last_seen`，不增加证据数。
5. 最新用户指令永远高于 memory。
6. memory 不能静默覆盖 spec、测试或实时数据。

## 7. Report Optimization Priority

如果要继续优化日报，优先级不是“先写 memory runtime”，而是：

### Priority 1: Report Acceptance Audit

先用当前 replay 输出建立验收清单。

验收面：

1. 前台是否 2 分钟可读？
2. `唯一重点对象` 是否唯一且一致？
3. `不做` 是否明确？
4. 附录是否重复前台？
5. 数据缺失是否诚实显示？
6. 盘中执行条件是否可操作？

### Priority 2: Structured History

补齐结构化历史，而不是解析旧 markdown。

重点：

1. `mainline_history_record`
2. `sector_turnover_snapshot`
3. `structure_mainline_records`
4. stock lifecycle rows
5. A-kill records

### Priority 3: Only-Focus Decision Audit

必须能解释为什么唯一对象是它。

需要输出或内部 atoms：

1. 候选来源。
2. 主线一致性。
3. 承接状态。
4. 资金痕迹。
5. 60 分钟确认条件。
6. 被排除对象的排除原因。

### Priority 4: Entry-Cycle Calibration

用 April 样本校准执行节点。

样本：

1. 成功：`中嘉博创`、`博杰股份`、`龙蟠科技`
2. 失败/反例：`石大胜华`、`甘肃能源`、`津药药业`

目标：

1. 不再统一机械 `max(入场价, 最近60分钟高点)`。
2. 不再把固定 `-5%` 当唯一止损。
3. 根据结构类型输出 stop mode。

### Priority 5: Workflow Memory

在上面四项验收清楚后，再做 workflow memory。

第一版只需要：

1. review artifact。
2. 手动 apply。
3. source-aware evidence。
4. hook 读取 validated memory。

不需要复杂调度器。

## 8. Skill Design

Skill 应该像 agent onboarding，不像命令行说明书。

### 8.1 SKILL.md 只保留路由

建议入口：

1. `generate_report`
2. `review_report_output`
3. `fix_report_defect`
4. `review_trade_case`
5. `extract_workflow_memory`
6. `optimize_skill`

这些可以是内部意图，不要求用户记。

### 8.2 References 一层展开

建议 references：

1. `report-contract.md`
2. `execution-rhythm.md`
3. `memory-governance.md`
4. `data-truthfulness.md`
5. `case-calibration.md`
6. `verification.md`

### 8.3 Scripts 只承担确定性任务

适合脚本化：

1. replay generation。
2. report audit。
3. memory extraction artifact generation。
4. memory apply。
5. structured history backfill。

不适合脚本化：

1. 用户意图判断。
2. 交易结论生成。
3. 是否把新经验晋升为长期规则。

## 9. Implementation Strategy

### Phase 0: Reset And Re-Spec

Status: current phase.

1. Keep `a1f9780` as baseline.
2. Preserve abandoned implementation branch for reference only.
3. Write this xhigh spec.
4. Do not resume previous implementation automatically.

### Phase 1: Report Acceptance Audit First

Goal:

- Build tests and/or audit scripts around the actual report output contract.

Tasks:

1. Add report-output audit fixture using current replay.
2. Assert front-page section order and uniqueness.
3. Assert no duplicate final/no-trade conclusion.
4. Assert data-source degraded values are not fake zeroes.
5. Assert unique focus consistency.

### Phase 2: Structured History Completion

Goal:

- Make mainline and turnover history real structured state.

Tasks:

1. Backfill recent snapshots with `mainline_history_record`.
2. Store sector-turnover snapshots from reliable atoms.
3. Render day-over-day `占比变化` when history exists.
4. Keep `待累计` when history is insufficient.

### Phase 3: Entry-Cycle Calibration

Goal:

- Make 60-minute confirmation and stop modes case-aware.

Tasks:

1. Build sample table for April cases.
2. Write tests for success and counterexample classification.
3. Output recommended stop mode.
4. Wire result into candidate entry plan.

### Phase 4: Workflow Memory Minimal Loop

Goal:

- Only after Phase 1-3, add a small memory loop.

Tasks:

1. Memory card schema.
2. Review artifact generation.
3. Manual apply.
4. Independent-source promotion rule.
5. Hook reads validated memory only by default.

### Phase 5: Skill Refactor

Goal:

- Make skill usable intuitively.

Tasks:

1. Add or rewrite `SKILL.md`.
2. Add references.
3. Keep command details out of main skill.
4. Verify skill contract with lightweight tests.

## 10. Non-Goals

1. Do not build a large memory platform first.
2. Do not add rigid command grammar for the user.
3. Do not auto-apply extracted memory without review.
4. Do not parse old markdown as primary structured history.
5. Do not let memory override latest user instruction.
6. Do not use workflow memory for stock observation continuity.
7. Do not treat passing unit tests as enough if replay markdown still reads wrong.

## 11. Acceptance Criteria

This spec is accepted when it makes the next implementation path clear:

1. The first implementation step is report acceptance audit, not memory infra.
2. The role of skill/spec/memory/ledger/artifact is distinct.
3. Memory promotion requires independent evidence.
4. Report optimization remains centered on trading decisions.
5. The user can keep speaking naturally without learning command grammar.
6. The checkpoint `a1f9780` remains a safe restore point.

