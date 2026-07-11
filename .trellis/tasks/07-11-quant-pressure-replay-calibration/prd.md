# 量化压力阶段离线回放校准

状态：✅ 实现与提交前审计完成（待用户确认提交）

## Goal

建立一套与正式日报隔离的五分钟压力阶段回放器，用历史前缀逐步重算价格与成交字段，验证它能否在完整“鸭蛋弧”出现前识别压力加速、第一轮降温、第二轮压力与修复，同时用保护样本控制误报。

## User Story

- **角色**：使用量化跟踪日报进行复盘和次日准备的个人交易者。
- **场景**：看到指数、板块或个股出现流畅下跌、第一轮快速压力或疑似量化退潮时。
- **目标**：区分当前动力、事件结构和证据完整度，而不是等收盘后用一条最像的公式解释全天。
- **成功标准**：每个五分钟检查点只使用当时及以前的数据；正例能复现已知事件顺序，普通下跌、快速修复和价格限制样本不会被误写成多轮交接。

### 用户旅程

1. 研究者载入一个冻结的五分钟样本，系统先校验来源、单位、时间语义和数据完整度。
2. 系统对每个已结束五分钟 bar 进行前缀回放，输出当前动力、事件结构、证据完整度和缺失原因。
3. 系统另外生成明确标记为事后诊断的整段曲线比较，不把全天拟合结果倒灌到盘中时间点。
4. 研究者比较正例与保护样本，决定是否值得进入更大规模样本外校准；本任务不修改正式日报。

## What I Already Know

- `wiki/资料库/量化跟踪日报公式工具箱.md` 已把公式分为日报压力阶段模型、研究曲线和机制假说。
- 现有“板块成交占比、板块宽度、核心承接、竞争方向”回答资金是否仍选择板块；本任务只研究价格与成交压力生命周期。
- `scripts/market_data/tushare_minute_service.py` 已定义统一分钟字段：`datetime/date/time/open/high/low/close/volume/amount`。
- `scripts/research/` 已有“纯构建函数 + Markdown 输出 + 独立测试”的研究模块模式。
- 当前仓库和本地 PostgreSQL 没有五个目标样本的耐久原始五分钟序列；Wiki 中只有派生结论，不能充当回放输入。
- 上证指数成交额与成交量之比不是指数点位的真实 VWAP；指数 VWAP 字段必须保持缺失。
- 五分钟 OHLCV/成交额只能识别压力路径，不能确认量化账户身份、真实订单流、剩余库存或 Hawkes 自激强度。
- 六个旧阶段词并非同一维度；底层必须拆成 `current_dynamics`、`episode_structure`、`evidence_status` 三条轴。

## Requirements

- [x] R1: 定义并冻结 `quant_pressure_replay.v1` 案例格式，原始行情与人工验收期望分离保存。
- [x] R2: 首轮样本矩阵包含两个压力路径正例和三个保护样本：`2026-05-21 上证指数`、`2026-07-10 兆易创新`、`2026-07-09 上证指数`、`2026-06-04 上证指数`、`2026-05-27 博云新材`。
- [x] R3: 每个案例保存证券类型、交易日、五分钟周期、时区、bar 时间含义、OHLCV/成交额单位与单段/累计语义、来源、查询日期和校验摘要；测试不得联网。
- [x] R4: 每个前缀时间点只使用该时间点及以前的 bar，输出 `as_of_bar`、候选变化时刻与实际发现时刻、前后斜率、当前动力、事件结构、证据完整度和缺失原因。
- [x] R5: 计算可由五分钟数据诚实支持的候选字段，包括对数价格斜率、变化点、成交额时间复核、个股 VWAP 驻留、单位成交下跌冲击代理、第一轮速度峰值、降温确认、修复比例、修复持续、第二轮压力和峰后不修复驻留。
- [x] R6: 未经单位验证的 VWAP/冲击代理、指数 VWAP、横截面同步、真实 `q/L`、订单流失衡、撤单、盘口深度、量化身份、量化成交占比和快慢资金身份一律输出 `null + reason`，不得以 `0` 补齐。
- [x] R7: 底层结果使用三条独立轴：`current_dynamics`、`episode_structure`、`evidence_status`；`handoff_risk_candidate` 只能作为派生结构解释，不能确认慢资金接棒。
- [x] R8: 整段曲线比较放在 `full_path_diagnostics`，明确标记为 `hindsight_only`；至少比较无变化线性基线、分段斜率、一般幂律/根号、指数、Gompertz 和对数稳健性对照。
- [x] R9: 提供纯计算入口 `build_quant_pressure_replay(case) -> dict` 和 Markdown 入口 `render_quant_pressure_replay_markdown(result) -> str`，并提供只读取本地 fixture 的命令入口。
- [x] R10: 输出不得包含仓位、买卖动作、量化成交占比、账户身份确认或正式日报字段写入。
- [x] R11: 参数使用版本化研究配置；两个极端正例不得用于反推目标日阈值，真实案例只固定事件先后和允许/禁止结论。

## Non-functional Requirements

### 性能

- 单个不超过 `48` 根五分钟 bar 的案例在本地 Python 3.14 下应于 `1` 秒内完成前缀回放和整段诊断。

### 可重复性

- 测试不访问网络、数据库或当前日期。
- 不新增 `scipy`、`ruptures` 等数学依赖；使用现有标准库或已安装依赖，并保持结果确定。

### 兼容性

- 所有 Python 命令固定使用 `.generated/venv-py314/bin/python3.14`。
- 新研究模块不改变 `scripts/replay/report_replay.py`、`scripts/domains/market_state/` 或正式日报产物。

## Acceptance Criteria

- [x] AC-R1-1: 五个 fixture 均通过 schema、日期、时间顺序、OHLC、单位和来源校验，原始输入不包含阶段标签或最佳公式。
- [x] AC-R2-1: 两个正例和三个保护样本均有独立的允许/禁止验收期望。
- [x] AC-R3-1: fixture 明确记录成交额/成交量是单段还是累计、各自单位和 bar 时间语义；无法验证时相关字段保持缺失。
- [x] AC-R4-1: 给任一案例追加未来极端 bar 后，原有每个 `as_of_bar` 的输出逐项不变。
- [x] AC-R4-2: 所有 `candidate_change_time <= first_detected_at`；首次发现时间一经形成不得由未来 bar 回填，候选后续漂移另记 `candidate_revised_at`。
- [x] AC-R5-1: 午休不计入九十分钟持续时间，斜率和驻留只使用交易 bar 序号。
- [x] AC-R5-2: OHLC 与成交额整体乘以同一正常数、成交量不变后，bp 斜率、VWAP 偏离和修复比例保持不变。
- [x] AC-R6-1: 上证案例的 VWAP 及驻留字段为 `null`，原因包含 `index_vwap_not_applicable`。
- [x] AC-R6-2: 缺少同行分钟数据时，`cross_section_sync` 为 `null`，原因包含 `requires_cross_section`。
- [x] AC-R7-1: `2026-07-10 兆易创新`先出现第一轮压力与降温，再允许出现第二轮结构；尾部未持续修复时不得输出修复候选。
- [x] AC-R7-2: `2026-05-21 上证指数`午后出现下跌压力跃迁；`14:40` 单次反弹不得确认修复，`14:55` 新低必须撤销修复解释。
- [x] AC-R7-3: `2026-07-09 上证指数`修复持续后不得继续保留负向交接风险或持续加速。
- [x] AC-R7-4: `2026-06-04 上证指数`不得把隔夜缺口直接算成盘中下跌加速。
- [x] AC-R7-5: `2026-05-27 博云新材`因价格限制和无有效盘中变化输出证据不足，不运行曲线身份判断。
- [x] AC-R8-1: `full_path_diagnostics.hindsight_only == True`，其中任何模型结果均不出现在此前的 `prefix_timeline`。
- [x] AC-R9-1: Markdown 明确分开前缀时间线、事后诊断、缺失证据和禁止推断。
- [x] AC-R10-1: 输出 schema 不包含仓位、买卖动作、量化成交占比或“卖方全部是量化”等字段。
- [x] AC-R11-1: 研究配置包含版本和来源说明，且不会从目标日完整结果自动反调参数。
- [x] AC-R11-2: 输出可由 `json.dumps(..., allow_nan=False)` 严格序列化；常数序列、小样本、零残差和非有限拟合均返回 `null + reason`。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] `design.md` / `implement.md` 已通过 review。
- [x] `research/findings.md` 保存本轮架构、字段和样本研究结论。
- [x] `implement.jsonl` / `check.jsonl` 已配置必要 spec 与 research 上下文。
- [x] 新增测试和限定回归测试通过。
- [x] `git diff --check` 通过。
- [x] PRD 状态改为 `✅ 实现与提交前审计完成`。
- [ ] 用户确认提交后，补充落地 commit。

## Out Of Scope

- 不接入正式日报 Markdown、HTML、LLM Wiki 自动注入或默认上下文。
- 不修改现有量化环境识别、板块成交占比、量化离场或候选选择逻辑。
- 不新增数据库表，不把个股分钟数据写入指数分钟表。
- 不建立正式生产阈值、评分、仓位或买卖动作。
- 不估计量化成交占比、账户身份、真实订单流、盘口深度或 Hawkes 自激强度。
- 不把两个极端案例用于宣称命中率或样本外有效性。

## Technical Notes

### 参考来源

- `wiki/资料库/量化跟踪日报公式工具箱.md`
- `wiki/资料库/异质临界值触发与流动性反馈模型.md`
- `wiki/资料库/烧柴理论-资金压力的峰值库存与半衰期.md`
- `wiki/资料库/2026-07-10兆易创新极端资金样本.md`
- `wiki/资料库/2026-05-21上证指数级联下跌样本.md`
- `.trellis/tasks/07-11-quant-pressure-replay-calibration/research/findings.md`

### 影响区域

- `scripts/research/quant_pressure_replay_runtime.py` — 新增离线纯计算与 Markdown 输出。
- `tests/test_quant_pressure_replay_runtime.py` — 新增字段、因果时间与样本回放测试。
- `tests/fixtures/quant_pressure_replay/` — 新增冻结原始样本与独立验收期望。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_quant_pressure_replay_runtime`
- `.generated/venv-py314/bin/python3.14 scripts/research/quant_pressure_replay_runtime.py --fixtures tests/fixtures/quant_pressure_replay`
- `git diff --check -- scripts/research/quant_pressure_replay_runtime.py tests/test_quant_pressure_replay_runtime.py tests/fixtures/quant_pressure_replay .trellis/tasks/07-11-quant-pressure-replay-calibration`

### 2026-07-11 Fresh Evidence

- `37` 项目标测试通过。
- `12` 项限定回归通过。
- 五个 fixture 的本地 CLI 完整运行通过。
- Python 3.14 `py_compile` 通过。
- 限定 `git diff --check` 通过。
- 数据因果、代码与测试、数学与事件语义三路独立提交前审计均无剩余问题。
- 最终代码 SHA256：`31604e989a6e7a79398ad139a247c1982a6d5b5d9481000c77ed872e393d333b`。
- 最终测试 SHA256：`db0419f59f5e7ac4018ac1a4d3b285dbbbc83c63ebd29d24f98f9ba2051671b8`。

## 落地 commit

待用户提交后回填。
