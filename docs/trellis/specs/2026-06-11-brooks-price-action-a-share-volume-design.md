# Brooks Price Action And A-Share Volume Localization

## Goal

Capture the local trading contract for combining Al Brooks' price-action-first
method with this project's A-share daily-report selection logic.

The outcome is not a new indicator stack. The outcome is a smaller decision
rule:

- price trend and common K-line behavior remain the final judge;
- volume is treated as A-share capital-expression evidence;
- volume can raise attention and identify who is acting, but participation still
  requires price follow-through, sector context, account fit, and the fixed
  execution windows.

## In Scope

- LLM Wiki knowledge for Brooks-style price action localized to A shares.
- Compact context mappings used by `build_llm_wiki_context()`.
- Explainable LLM Wiki routing terms for questions about volume, amount, and
  capital expression.
- Narrow tests proving the wiki and routing contract are present.

## Out Of Scope

- Changing candidate scoring weights.
- Adding a new volume indicator model.
- Changing report generation runtime or replay data sources.
- Expanding execution windows.
- Treating Brooks' method as a full replacement for sector-anchor reversal,
  leader debate, or final target resolution.

## Non-Goals

- Do not build a "perfect stock" filter requiring every learned condition to
  pass.
- Do not make volume a standalone buy reason.
- Do not make indicators a substitute for price trend, common K-lines, and
  follow-through.

## Design

### Principle

Brooks' method says the chart already reflects the market's judgment, and
indicators are mostly transformations of price. In highly liquid U.S. futures,
he can often trade with K-lines and a 20-period moving average.

This project keeps that principle but localizes it for A shares:

- `price_is_final_judge`: price trend, K-line close, breakout, pullback, and
  failure decide whether the market accepted the idea.
- `volume_is_capital_expression`: volume shows whether funds are acting, but it
  must be interpreted through price consequence.
- `indicator_combo_downgrade`: MACD, KDJ, custom combinations, and pretty
  factor stacks cannot create participation by themselves.
- `volume_first_for_attention_not_action`: volume may be checked early to find
  capital attention, but action comes only after price confirmation.

### Volume-Price Quadrants

| Situation | Interpretation | Action Contract |
|---|---|---|
| Volume expansion + rising price + strong close + sector sync | Funds are attacking and price accepts the attack | Can enter comparison for participation if account and window fit |
| Volume expansion + upper shadow / fade / failed close | Funds acted, but supply or disagreement appeared | Downgrade to observation or existing-position risk handling |
| Shrinking-volume pullback + trend still intact + reclaim | Healthy digestion or controlled pullback | Watch for second confirmation, not automatic buy |
| Volume expansion + breakdown / failed reclaim | Active sell pressure or stampede risk | Risk first; do not use cheap price as a reason |
| Sudden low-position volume expansion | Funds started to express interest | Research and observation priority only; needs follow-through |
| No-volume rise or one-line limit-up | Result is strong but tradability is poor | Treat as leader/sector evidence; do not assume executable entry |

### Integration Point

The daily-report selection path remains:

```text
market cycle -> mainline/sector path -> sector-anchor reversal -> leader debate
-> Brooks price-action judge -> common-selection consistency -> account/time/risk
-> final_target_resolution
```

The localized volume rule enters inside `Brooks price-action judge`. It does not
replace `sector-anchor reversal` or `leader debate`.

## Brooks A-share Volume-Localized Selection Flow

```mermaid
flowchart TD
    N0["N0 数据封装<br/>行情 / 成交量 / 板块 / 候选 / 持仓 / 风险快照"] --> N1["N1 市场周期判断<br/>退潮 / 修复 / 主升 / 震荡"]
    N1 --> N2["N2 资金方向判断<br/>主线成交占比 / 赚钱效应 / 资金集中方向"]
    N2 --> N3["N3 板块关系拆解<br/>中军 / 弹性核心 / 后排 / 高标反馈"]
    N3 --> N4["N4 板块内角色识别<br/>板块锚 / 分支龙头 / 中军 / 跟风 / 套利"]
    N4 --> N5["N5 候选池归一<br/>昨日极度看好 / 主线核心 / 次核心 / 龙头回头 / 持仓"]

    N5 --> N6["N6 反推龙头<br/>先问为什么做它，再问为什么不做板块锚"]
    N6 --> D1["龙头反向辩论<br/>正方：辨识度 / 板块锚 / 速度档 / 承接路径<br/>反方：A杀 / 弱反抽 / 长上影 / 风险项 / 后手成本"]

    D1 --> B0["布鲁克斯价格行为裁判"]
    B0 --> B1["价格趋势优先<br/>价格是最终裁判，指标组合只作辅助"]
    B0 --> B2["常用K线审查<br/>实体 / 影线 / 收盘 / 突破 / 回撤 / 失败"]
    B0 --> B3["趋势-交易区间谱系<br/>强趋势 / 普通趋势 / 宽幅通道 / 交易区间"]
    B0 --> B4["A股量价本地化<br/>成交量是资金表态，价格确认表态是否被接受"]

    B4 --> V1["放量上涨 + 强收盘 + 板块同步<br/>进攻证据"]
    B4 --> V2["放量冲高回落 / 长上影<br/>分歧或供应证据"]
    B4 --> V3["缩量回踩 + 趋势未破<br/>等二次确认"]
    B4 --> V4["放量破位 / 收不回<br/>先处理风险"]

    B1 --> N7["N7 候选对照淘汰"]
    B2 --> N7
    B3 --> N7
    V1 --> N7
    V2 --> N7
    V3 --> N7
    V4 --> N7

    N7 --> C1["共同选择一致性<br/>昨日持筹者 / 明日新买盘 / 主线资金 / 量化动量"]
    C1 --> N8["N8 仓位与执行条件<br/>账户适配 / 交易者等式 / 时间窗口 / 失效线"]
    N8 --> R1["final_target_resolution<br/>新开仓对象 / 旧仓处理对象 / 观察对象 / 最终显示对象"]
    R1 --> N9["N9 输出一致性复核<br/>0%不参与、50%条件执行、100%核心进攻前后一致"]
    N9 --> O["日报输出<br/>市场结构 / 主线与龙头推导 / 个股解读 / 明日执行计划 / 最终结论"]
    O --> P["复盘回写<br/>判断样本 / 错题本 / LLM Wiki"]
```

### Wrong vs Correct

Wrong:

```text
Volume expands -> funds are in -> buy.
```

Correct:

```text
Volume expands -> funds expressed interest -> check price consequence:
strong close, follow-through, sector sync, account fit, fixed window, and
invalidation. Without those, it remains observation.
```

Wrong:

```text
Brooks ignores volume -> A-share reports should ignore volume.
```

Correct:

```text
Brooks downgrades indicators because price is the final judge. A-share volume is
not promoted above price; it is used as capital-expression evidence that still
needs price acceptance.
```

## Done Definition

- Wiki records the Brooks/A-share volume relationship.
- Context mappings include price-first, volume-as-capital-expression, and
  volume-price quadrant rules.
- Router can match volume/amount/capital-expression questions to the Brooks
  price-action node.
- Tests verify the contract.

## Verification

Run:

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_context tests.test_llm_wiki_router
```
