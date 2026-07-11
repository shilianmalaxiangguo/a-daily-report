# Design: 量化压力阶段离线回放校准

## Scope And Boundaries

本任务新增独立研究模块，不进入正式日报生成、历史日报 replay、市场状态判断、候选筛选或仓位链路。

新增边界：

- `scripts/research/quant_pressure_replay_runtime.py`：标准化、前缀回放、事后诊断和 Markdown 输出。
- `tests/fixtures/quant_pressure_replay/raw/*.json`：冻结不可变分钟事实。
- `tests/fixtures/quant_pressure_replay/expectations.json`：与输入分离的人工验收期望。
- `tests/test_quant_pressure_replay_runtime.py`：纯本地测试。

明确不复用：

- `scripts/replay/sector_forward_replay.py` 的分钟标准化会丢失 `volume/amount`。
- `scripts/replay/report_replay.py` 会装配正式历史日报，不属于本研究边界。
- `scripts/domains/market_state/quant_environment_detector.py` 与 `sector_turnover_trend_tracker.py` 是现有日级口径，不作为压力阶段模型基础。

## Contracts / Data Flow

```text
冻结原始 fixture
  -> 输入与单位校验
  -> 标准化交易 bar 序号
  -> 对每个前缀独立计算字段
  -> 三轴结果 + 缺失原因
  -> prefix_timeline

完整单日序列
  -> 分段/平滑曲线比较
  -> full_path_diagnostics(hindsight_only=true)

两者 + 独立 expectations
  -> 单元测试 / Markdown 研究报告
```

### 输入契约 `quant_pressure_replay.v1`

```python
{
    "schema_version": "quant_pressure_replay.v1",
    "case_id": "str",
    "origin": "observed | synthetic",
    "instrument": {
        "code": "str",
        "name": "str",
        "type": "stock | index",
    },
    "trade_date": "YYYY-MM-DD",
    "bar_period_minutes": 5,
    "previous_close": "float | null",
    "price_limit_state": "none | limit_up | limit_down | unknown",
    "source": {
        "provider": "str",
        "query_date": "YYYY-MM-DD",
        "source_date": "YYYY-MM-DD",
        "timezone": "Asia/Shanghai",
        "bar_time_semantics": "interval_end",
        "volume_unit": "shares | lots | unknown",
        "amount_unit": "CNY | CNY_10K | unknown",
        "volume_semantics": "interval | cumulative | unknown",
        "amount_semantics": "interval | cumulative | unknown",
        "source_url": "str",
    },
    "minute_bars": [
        {
            "datetime": "YYYY-MM-DD HH:MM:SS",
            "open": "float",
            "high": "float",
            "low": "float",
            "close": "float",
            "volume": "float | null",
            "amount": "float | null",
        }
    ],
    "annotations": {"facts_only": []},
}
```

输入不得保存 `current_dynamics`、最佳公式或 RMSE。人工允许/禁止结果只存在 `expectations.json`。

### 输出契约

```python
{
    "schema_version": "quant_pressure_replay_result.v1",
    "case_id": "str",
    "data_quality": {...},
    "config": {"version": "research.v1", ...},
    "prefix_timeline": [
        {
            "as_of_bar": "datetime",
            "metrics": {
                "candidate_change_time": "datetime | null",
                "first_detected_at": "datetime | null",
                "candidate_revised_at": "datetime | null",
                ...
            },
            "current_dynamics": "accelerating | steady_down | decelerating | repairing | unclear",
            "episode_structure": "first_burst_open | first_burst_completed | nonrepair_tail | second_wave | flash_candidate | unclear",
            "evidence_status": "sufficient | partial | insufficient",
            "handoff_risk_candidate": "bool | null",
            "missing_evidence": [{"field": "str", "reason": "str"}],
        }
    ],
    "full_path_diagnostics": {
        "hindsight_only": True,
        "models": {...},
    },
    "forbidden_inferences": [...],
}
```

未知值必须使用 `null + reason`。原因至少覆盖：

- `insufficient_prefix`
- `index_vwap_not_applicable`
- `amount_unit_unverified`
- `volume_unit_unverified`
- `episode_not_completed`
- `requires_order_flow`
- `requires_cross_section`
- `future_horizon_censored`
- `price_limit_path_not_identifiable`

## Prefix Computation

### 时间与价格

- 使用固定 A 股五分钟交易时段映射交易序号，只压缩午休；盘中缺 bar 标记数据不完整，不能靠已观察行号把缺口压缩掉。
- 使用 `log(close)` 对交易序号回归，斜率换算为 `bp/5分钟`。
- 隔夜缺口由 `previous_close -> first open` 单独记录，不进入盘中斜率。

### 变化点

- 每个前缀仅扫描已经出现的候选位置。
- 候选位置左右必须各有最小窗口。
- 比较无变化线性模型与连续折线模型的惩罚损失改善。
- 同时保留候选变化起点 `candidate_change_time`、首次发现时刻 `first_detected_at` 与候选漂移时刻 `candidate_revised_at`。
- 首次发现时刻必须经过版本化的持续 bar 要求，形成后保持冻结；候选后续漂移不能回填更早发现时间，也不能改写过去前缀。

### VWAP

- 仅 `instrument.type == stock` 且 `amount_unit == CNY`、`volume_unit == shares`、两者均为单段值时计算累计 VWAP。
- 指数全部 VWAP 字段为 `null`，原因 `index_vwap_not_applicable`。
- `index_vwap_not_applicable` 属于不适用，不是本应存在却缺失，不能单独降低价格路径的 `evidence_status`。
- 成交单位未经验证时，不猜换算比例。

### 单位成交下跌冲击代理

\[
impact=10^4[-(\log C_t-\log C_{t-w})]_+ / \sum amount_{t-w+1:t,yi}
\]

该值只表示每亿元无方向总成交对应的净下跌 bp，不代替主动卖出额、订单流失衡或盘口深度。成交额语义或单位未知时保持缺失。

### 第一轮、降温与第二轮

- 速度峰值与价格低点分开保存。
- 第一轮速度峰值只能在峰后速度持续下降后确认。
- 第二轮必须发生在第一轮降温确认之后；连续加速不得拆成两轮。
- `recovery_ratio_current` 不截断，创新低可以为负，完全修复可以超过 `1`。
- 一根反弹不能确认修复；新低出现后立即撤销此前修复候选。

### 三轴结果

- `current_dynamics`：描述此刻动力。
- `episode_structure`：描述已观察到的事件结构。
- `evidence_status`：描述结论完整度。
- `handoff_risk_candidate`：只由第一轮降温、弱修复与第二轮/不修复长尾派生，不确认资金身份。

研究阈值集中在版本化 `ResearchPressureConfig` 中。首版参数用于验证计算与事件顺序，不是生产阈值；不得从两个目标正例的完整路径自动反调。

## Full Path Diagnostics

事后诊断比较：

- 无变化线性基线。
- 一个或多个候选变化点的连续折线。
- 一般有限时刻幂律，单独记录 `m` 是否接近 `0.5`。
- 指数加速。
- Gompertz 单轮招募与耗尽。
- 对数稳健性对照。

每个模型返回参数、RMSE、AICc 和适用性说明。所有模型拟合同一组完整观测的对数价格响应；分类使用未舍入值，舍入只用于输出。模型参数域必须有界，指数运算防溢出，稳定处理并列排名。`n <= k + 1`、常数序列、零残差或非有限结果时，AICc / 排名返回 `null + reason`。首版分段模型只比较一个变化点；模型排名只能描述完整路径，不进入 `prefix_timeline`。

原始 fixture 的 `validation_summary` 保存选中源行哈希、预期交易时段、日 OHLC、日成交量/成交额及容差检查。人工事件期望只保存在独立 `expectations.json`。

## Sample Matrix

| 案例 | 作用 | 主要验收 |
|---|---|---|
| `2026-05-21 上证指数` | 正例：慢压后阶段跃迁 | 午后加速；14:40 一次反弹不确认修复；14:55 新低撤销修复解释 |
| `2026-07-10 兆易创新` | 正例：两轮压力 | 第一轮降温后才允许第二轮；尾部近低收盘不升级修复 |
| `2026-07-09 上证指数` | 快速修复保护 | 修复持续后不保留负向交接或持续加速 |
| `2026-06-04 上证指数` | 隔夜缺口保护 | 隔夜缺口不进入盘中下跌斜率 |
| `2026-05-27 博云新材` | 信息重估/价格限制保护 | 无有效盘中曲线时输出证据不足，不确认程序化级联 |

两个正例只属于“压力路径正例”，不是“量化身份正例”。

## Compatibility / Migration

- 无数据库迁移，无正式报告 schema 变化。
- 测试 fixture 不是正式日报读取路径。
- 未来若接正式日报，指数分钟数据可复用现有 `index_minute_bars`；个股分钟持久化必须另行设计通用证券分钟表。
- 未来横截面同步必须使用目标日期的成分与权重，不能使用当前成分倒推历史。

## Tradeoffs

### 选择前缀回放而非收盘后拟合

代价是信号出现更晚、字段更容易保持不确定；收益是能诚实检验是否存在提前识别价值。

### 选择三轴结果而非单标签

代价是输出多三个字段；收益是允许同时表达“第二轮压力且仍在加速”，不会把事件结构与当前动力互相覆盖。

### 选择五个小样本而非立即扩大抓取

代价是不能估计命中率；收益是先验证契约、未来信息隔离和保护样本，再决定是否值得建设数据层。

### 选择确定性回归/网格搜索而非新增数学依赖

代价是算法不追求最优性能；收益是环境稳定、结果可重复、实现范围可控。

## Rollback / Roll-forward

- 回滚：删除新增研究模块、测试和 fixture；正式日报行为不受影响。
- 向前推进：只有真实保护样本通过且信号早于完整曲线，才另开任务扩大样本；再之后才讨论日报研究段接入。
