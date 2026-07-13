# Design: 日报指数目标日双源核对

## Scope And Boundaries

本任务只保护日报展示的六个指数。主来源仍是现有 Tushare-first 路径；腾讯日 K 只用于独立核对，不参与候选、仓位或执行动作计算。

核对发生在六个指数采集完成后、报告构建前。报告生成前检查再次验证结构化核对事实与当前载荷一致，防止保存、回读或后续加工把已核对值替换掉。

## Contracts / Data Flow

```text
Tushare index_daily
  -> 保留 trade_date/pre_close/pct_chg
  -> 只选择 target_date 日线
  -> 六个报告指数载荷
                         \
                          -> 逐指数核对 -> index_cross_validation.v1
                         /
Tencent fqkline day
  -> 目标日 + 前一交易日

index_cross_validation.v1 + 当前六指数载荷
  -> 日报生成前检查
  -> 全部通过：继续渲染
  -> 任一失败：停止生成并输出失败明细
```

### 六指数映射

| 报告名称 | 主来源代码 | 腾讯代码 | 报告载荷位置 |
|---|---|---|---|
| 上证指数 | `000001.SH` | `sh000001` | `indices.上证指数` |
| 深证成指 | `399001.SZ` | `sz399001` | `indices.深证成指` |
| 创业板指 | `399006.SZ` | `sz399006` | `indices.创业板指` |
| 中证全指 | `000985.CSI` | `sh000985` | `wind_a_alternative` |
| 中证500 | `000905.SH` | `sh000905` | `csi500_index` |
| 中证1000 | `000852.SH` | `sh000852` | `csi1000_index` |

### 核对事实契约

```python
{
    "schema_version": "report_index_cross_validation.v1",
    "target_date": "YYYY-MM-DD",
    "status": "success | failed",
    "primary_provider": "mixed",
    "verification_provider": "tencent.fqkline.day",
    "tolerances": {
        "price_abs": 0.05,
        "change_pct_abs": 0.02,
    },
    "checks": [
        {
            "name": "上证指数",
            "code": "000001",
            "status": "success | failed",
            "primary": {
                "provider": "tushare.index_daily",
                "trade_date": "YYYY-MM-DD",
                "close": 0.0,
                "pre_close": 0.0,
                "change_pct": 0.0,
            },
            "verification": {
                "provider": "tencent.fqkline.day",
                "trade_date": "YYYY-MM-DD",
                "close": 0.0,
                "pre_close": 0.0,
                "change_pct": 0.0,
            },
            "close_diff": 0.0,
            "change_pct_diff": 0.0,
            "reason": "str",
        }
    ],
    "failures": ["str"],
}
```

### 通过条件

- 六个固定名称各有且仅有一项核对明细。
- 每项名称与代码必须匹配固定清单；不得有重复项或未知代码。
- 主来源与腾讯来源 `trade_date` 都等于目标日期。
- 两侧 `close`、`pre_close` 和 `change_pct` 都是有效数值。
- `abs(primary.close - verification.close) <= 0.05`。
- `abs(primary.change_pct - verification.change_pct) <= 0.02` 个百分点。
- 顶层 `failures`、成功明细的 `reason` 必须为空，保存的三项差异必须与两侧事实重新计算的结果一致。
- 生成前检查时，当前报告载荷的日期、收盘和涨跌幅仍与核对事实中的主来源一致。

任一条件不满足时不选择“更可信的一边”，而是停止生成并保留差异证据。

## Integration Points

1. `market_data/tushare_service.py` 保留指数原始前收、涨跌额、涨跌幅和成交额字段。
2. `input/tushare_runtime.py` 的指数载荷构建只接受目标日，并输出前收和源涨跌幅。
3. 新增一个小型指数核对模块，负责腾讯日 K 获取、标准化、逐项比较和核对事实完整性检查。
4. `domains/market_state/request.py` 仅在契约生效日期后，于六个指数采集完成时调用核对函数，写入结果、采集状态和请求日志；更早日期的新采集不创建该事实。
5. `daily_report_render.py` 把主要指数、中证500和指数交叉核对纳入关键数据检查，并核对目标日期及证据一致性。
6. PostgreSQL 继续通过现有通用事实持久化保存核对事实；不新增表或迁移。

## Compatibility / Migration

- 对现有指数载荷只增加字段，不移除旧字段。
- 契约从报告日期 `2026-07-13` 起强制生效；更早日期若已有核对事实也必须验证，批量迁移旧历史事实另行处理。
- `2026-07-13` 使用重新采集的目标日事实覆盖本次错误数据。
- 不改变现有输出路径、报告标题和命令参数。

## Tradeoffs

- 腾讯接口不可用时会停止生成，即使 Tushare 数据看起来合理。这是用户明确要求的真实性优先选择。
- 固定绝对点位容差用于吸收腾讯三位小数与 Tushare 四位小数差异；不放宽到足以掩盖交易日错位。
- 核对证据会增加少量 PostgreSQL 事实字段，但无需新增数据库结构。

## Rollback / Roll-forward

- 回滚时可移除市场请求中的核对调用和生成前检查项；新增载荷字段为兼容性字段，可保留。
- 若腾讯接口协议变化，先修复解析并保持失败停止，不临时绕过核对。
- 后续如需扩大到其他市场事实，应另建任务，不在本次实现中增加通用多源框架。
