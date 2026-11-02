# 历史兼容测试

当前策略验收使用 references/verification.md 的明确清单；不使用全仓自动发现来裁定现行策略。

legacy_llm_wiki_context、hook、lint、manifest、router 五个模块保留清理时旧知识图谱测试的代码（其中包括此前工作区修改）。原路径、当前 SHA256、HEAD SHA256 及差异标记见 docs/archive/daily-report-framework/2026-11-02/historical-tests-manifest.json。不将重命名说成测试通过，不删除旧断言来伪造通过。

旧 manifest 的完整仓库案例依赖旧 Wiki 的相对路径，context 也直接读取旧知识页。当前 Wiki 已没有这些文件；复核旧行为须在对应历史版本或冻结夹具环境执行，不能把归档知识恢复到当前 Wiki 来满足旧断言。纯夹具测试仍可按具体测试名独立执行。本轮不声称这五个历史模块通过。

test_decision_board 和 test_daily_extras 内的旧候选、五日算法及多策略回测仅用于历史兼容；同模块的当前排除检查由 test_current_strategy_scope 覆盖。保留旧计算不意味着重新启用。

当前入口隔离由 test_current_entry_isolation 在独立解释器中验证，避免仅测试历史兼容模块而遗漏真实 CLI。

2026-11-02另将51份旧选股、账户、执行链和完整版展示模块改名为 `legacy_test_*.py`，退出 `test*.py` 默认发现。文件逐字节保留；原路径、新路径、工作区SHA256、HEAD SHA256及差异见 [迁移清单](../docs/archive/daily-report-framework/2026-11-02/retired-strategy-tests-manifest.json)。清单记录重命名事实，不代表这些历史测试通过。compact历史提取测试仍显式引用其中的期货夹具。

阿尔法／贝塔研究保留 `tests.test_market_alpha_beta`、`tests.test_decision_board`、`tests.test_daily_extras` 及其算法和证据；后两个模块包含历史建议，只在明确研究时运行。当前市场事实、来源校验和小盘测试保留原名称。全仓仍有其他历史兼容测试，不能把默认发现当成当前策略验收清单，也不能为通过历史测试恢复旧要求。

默认 `rg` 搜索排除冻结档案、上述历史测试和已冻结旧方案。查证历史时用 `rg --no-ignore <关键词> <明确路径>`；`.rgignore` 不影响Git保留或Python显式导入。
