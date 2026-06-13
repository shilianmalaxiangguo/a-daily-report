# brainstorm: 汰弱留强交易原则入库

## Goal

把用户提出的“指数汰弱留强、散户常汰强留弱”沉淀成日报可复用的交易思想：面对 `长电科技 or 华电辽能` 这类问题，日报和盘中问答必须做旧仓资格、新机会强度、账户资金优先级的相对比较，而不是只把新票写成观察对象。

## What I already know

* 用户明确认为这和刚才的持仓取舍问题是同一套思想，不只是观察 `长电科技`。
* 现有 `wiki/交易思想/价格行为与能量框架.md` 已有“去弱留强与盈亏分离”“防双重亏损”“小资金优势校准”。
* 现有 `wiki/交易思想/做T与风险控制.md` 已有 `长电科技` / `华电辽能` 的 T+1 模式边界校准。
* `scripts/knowledge/llm_wiki_context.py` 是日报运行时可直接取用的 LLM Wiki 压缩投影。
* `scripts/knowledge/llm_wiki_router.py` 已支持把日报事实路由到可解释知识命中。

## Assumptions

* 本次只沉淀稳定原则，不重新生成历史日报，不跑 replay，不修改持仓报告前台。
* “汰弱留强”可以作为“去弱留强”的上位认知表达，但落到交易动作时仍必须保留三窗口、MA/VWAP、承接、失效条件和账户承受力。
* `华电辽能` 与 `长电科技` 的结论不应写成固定谁强谁弱，而应写成判断顺序和资金取舍规则。

## Requirements

* Wiki 必须明确：指数编制的启发是保留被市场继续选择的强者，处理掉队或逻辑失效的弱者。
* Wiki 必须明确反面错误：卖掉仍强的票去补亏损弱票，是散户式汰强留弱。
* Wiki 必须明确旧仓和新机会分离：先判旧仓是否仍有持仓/做T资格，再判新机会是否更强，最后决定资金优先级。
* LLM Wiki 压缩投影必须包含这条规则，让日报运行时可以在候选取舍中取用。
* 路由层必须能在 `final_target_resolution` 或显式问题里命中该知识。
* 测试必须覆盖 wiki 文本、LLM context、路由命中。

## Acceptance Criteria

* [ ] `价格行为与能量框架.md` 出现“汰弱留强 / 汰强留弱 / 长电科技 or 华电辽能”的稳定规则。
* [ ] `做T与风险控制.md` 明确做T不能成为留弱票或补弱票的理由。
* [ ] `llm_wiki_context` 暴露旧仓新机会分离、强弱资金优先、汰弱留强反面错误。
* [ ] `llm_wiki_router` 能从旧仓和新机会事实命中资金优先级知识。
* [ ] Focused unittest 通过。
* [ ] `git diff --check` 通过。

## Definition of Done

* 文档、LLM 投影和测试同步更新。
* 不新增数据源，不生成新 replay 快照。
* 不覆盖正式日报或 replay 产物。
* 不触碰无关未提交改动。

## Out of Scope

* 不给 `长电科技` 或 `华电辽能` 写固定的买卖结论。
* 不改日报候选筛选算法。
* 不改仓位管理报告前台。
* 不新增打分引擎或新执行层。
* 不把文章原文扩写成理论长文放进日报。

## Technical Notes

* 主要写入路径：`wiki/交易思想/价格行为与能量框架.md`、`wiki/交易思想/做T与风险控制.md`。
* 运行投影路径：`scripts/knowledge/llm_wiki_context.py`。
* 可解释路由路径：`scripts/knowledge/llm_wiki_router.py`。
* 重点测试：`tests/test_llm_wiki_context.py`、`tests/test_llm_wiki_router.py`。
* Python 命令必须使用 `.generated/venv-py314/bin/python3.14`。
