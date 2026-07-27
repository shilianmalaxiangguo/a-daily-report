# Implementation: B1/B2 与集合竞价 1x 执行回测

## Prerequisites

- 已确认样本为 14 笔全样本、12 笔统一字段样本。
- 已冻结 `research/execution-protocol.md` 的阈值；看见结果后不得在本轮调参。
- Python 固定使用 `.generated/venv-py314/bin/python3.14`。
- 现有工作区大量未提交修改不属于本任务；只新增约定路径，不覆盖、不格式化其他文件。

## Ordered Checklist

- [x] I1: 新增离线优先的研究脚本与不可变决策清单，先写单测锁定时间因果、仓位与分类。
- [x] I2: 实现显式 `--collect` 通达信采集，冻结 14 笔所需日线与一分钟事实，验证 240 分钟网格和同源日线一致性。
- [x] I3: 实现开盘位置、早盘路径、累计 VWAP、B1/B2 触发、下一分钟成交和统一退出。
- [x] I4: 实现五种执行方式、费用、MFE/MAE、2 万元一手可成交性、全样本/保护样本/分场景汇总。
- [x] I5: 从同一 JSON payload 生成 Markdown，包含方法、决策矩阵、总体结果、分场景结果、逐笔明细、反例和限制。
- [x] I6: 运行测试、离线重复生成、SHA-256 稳定性、任务校验和差异检查。
- [x] I7: 对照 PRD 做独立审计；只修本任务范围内发现的问题。
- [x] I8: 冻结上证同源日线与一分钟事实，新增账户容量约束下的标准化/整手逐日账本、同持有时段基准与逐日超额。
- [x] I9: 将累计收益首页与逐日重叠明细改为账本结果，补充重叠、隔夜、费用、容量和基准缺失回归测试，重新执行全部验证。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_b1_b2_auction_backtest`
- `.generated/venv-py314/bin/python3.14 scripts/research/b1_b2_auction_backtest.py --collect --fixture tests/fixtures/b1_b2_auction_backtest/cases.json`
- `.generated/venv-py314/bin/python3.14 scripts/research/b1_b2_auction_backtest.py --fixture tests/fixtures/b1_b2_auction_backtest/cases.json --output-json reports/research/b1-b2-auction-backtest-20260721.json --output-md reports/research/b1-b2-auction-backtest-20260721.md`
- 重复上一命令并用 `shasum -a 256` 比较 JSON 与 Markdown。
- `.generated/venv-py314/bin/python3.14 ./.trellis/scripts/task.py validate .trellis/tasks/07-21-b1-b2-auction-backtest`
- `git diff --check -- .trellis/tasks/07-21-b1-b2-auction-backtest scripts/research/b1_b2_auction_backtest.py tests/test_b1_b2_auction_backtest.py tests/fixtures/b1_b2_auction_backtest reports/research/b1-b2-auction-backtest-20260721.json reports/research/b1-b2-auction-backtest-20260721.md`

## Risk And Rollback Points

- 数据采集是本任务唯一联网步骤；任何目标日缺少 240 条分钟或日线不一致时停止该样本，不换源拼接。
- 报告解析路径只读明确 T0 字段；若报告内容在任务期间变化，fixture 中保留的源摘要哈希应暴露差异。
- 触发阈值改动会改变全部结果；本轮结果生成后不改阈值。需要修改时新建版本和保护样本。
- 回滚只删除本任务新增路径，不触碰既有未提交修改。

## Review Checkpoints

- 采集后抽查最早样本、中间样本、华天科技样本的交易日、首尾分钟、日线交叉检查。
- 分析后抽查至少一笔开盘直接更优、一笔等待确认更优和一笔未触发样本。
- 最终检查 14/12 样本计数、五种执行方式仓位上限、T+1限制、共同退出价与费用假设。
