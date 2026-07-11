# Implementation: 量化压力阶段离线回放校准

## Prerequisites

- 任务保持规划状态，用户确认本 PRD / design / implement 边界后再运行 `task.py start`。
- 实现前加载 `trellis-before-dev`，并重新读取相关 backend spec 与本任务 research。
- 所有 Python 命令使用 `.generated/venv-py314/bin/python3.14`。
- 不修改工作区已有的日报主链文件和其他用户改动。

## Ordered Checklist

- [x] I1: 生成 `tests/fixtures/quant_pressure_replay/raw/` 五个来源明确的原始 fixture，并创建独立 `expectations.json`；校验条数、交易日、时间顺序、OHLC、单位和源日成交额一致性。
- [x] I2: 先新增失败测试，覆盖 schema、单位、指数 VWAP 缺失、固定交易时段/午休、盘中缺 bar、隔夜缺口、价格限制、未知值原因和三轴枚举。
- [x] I3: 实现输入标准化、数据质量和研究配置契约。
- [x] I4: 先新增前缀不变、首次发现冻结/候选漂移、价格与成交额同步尺度不变测试，再实现增量斜率、变化点、成交额时间和冲击代理。
- [x] I5: 先新增第一轮/降温/第二轮/修复撤销测试，再实现事件字段和三轴派生；连续加速不得拆成第二轮。
- [x] I6: 实现 `full_path_diagnostics(hindsight_only=true)`，在同一对数价格响应上比较线性、单变化点分段、幂律/根号、指数、Gompertz 和对数；覆盖小样本、常数序列、零残差、非有限结果和稳定并列，确保结果不进入历史前缀。
- [x] I7: 实现 `build_quant_pressure_replay(case)`、Markdown 渲染和本地 fixture 命令入口。
- [x] I8: 对五个真实样本运行验收，记录允许/禁止结论；失败时优先扩大不确定结果，不为命中正例调整单日阈值。
- [x] I9: 运行限定测试、完整新测试、CLI、`git diff --check` 和提交前审计；更新本任务 research 与 PRD 状态。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_quant_pressure_replay_runtime`
- `.generated/venv-py314/bin/python3.14 scripts/research/quant_pressure_replay_runtime.py --fixtures tests/fixtures/quant_pressure_replay`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_margin_pressure_index_relation tests.test_intraday_execution_runtime`
- `git diff --check -- scripts/research/quant_pressure_replay_runtime.py tests/test_quant_pressure_replay_runtime.py tests/fixtures/quant_pressure_replay .trellis/tasks/07-11-quant-pressure-replay-calibration`

## Risk And Rollback Points

- Fixture 单位错误会污染 VWAP 和冲击代理；I1 验证未通过时停止实现。
- 未来信息泄漏是首要风险；任何前缀不变测试失败都停止继续分类调试。
- 变化点过度拟合时，优先输出 `unclear/partial`，不增加隐藏阈值。
- 保护样本被误判时，不为正例命中保留旧规则；回到字段定义或降低结论层级。
- 不触碰正式日报链路，因此回滚只涉及新增文件和本任务 Wiki 契约修正。

## Review Checkpoints

- RC1: fixture 来源、单位、时间语义和独立 expectations 审计。
- RC2: 前缀不变与未知值语义审计。
- RC3: 两个正例与三个保护样本的事件顺序审计。
- RC4: 输出字段不含账户身份、量化占比、仓位和买卖动作。
- RC5: 用户确认回放结果后，才另行讨论扩大样本或接入日报研究段。
