# 2026-06-10 日报次日归因闭环规格

状态：✅ 已执行

## Goal

在已经修复最终对象身份一致性的基础上，新增“次日归因闭环”规格，把最终观察对象、过程候选、历史证据和未胜出候选分层结算，避免把雅克科技、金安国纪、双星新材、中船特气这类不同身份样本混成一个胜率结论。

## In Scope

- 基于 `reports/2026-06-10_次日归因闭环_mermaid.html` 的链路重新定义次日归因字段。
- 明确最终观察对象、明日执行对象、过程候选、候选观察补充、历史证据的结算桶。
- 约束 0% 或仅观察报告的次日上涨不能记为执行命中。
- 要求次日行情事实带 `review_date`、`source_name`、`source_quote_time` 或等价来源字段。
- 后续实现时，把强票和失败票都纳入同一张归因表，不只展示涨得好的样本。

## Out of Scope

- 不重写候选池评分、排序、板块锚反推或最终对象算法。
- 不把今天的走势反向写成 2026-06-10 当时的买入资格。
- 不新增自动交易、回测框架或券商执行逻辑。
- 不覆盖现有正式日报；本规格先定义后续新增字段和验收。

## Non-goals

- 不证明某只个股“必然正确”。
- 不用单日涨跌直接评判整套选股逻辑已经稳定胜出。
- 不隐藏双星新材这类失败过程样本。
- 不把历史观察证据包装成当前最终对象。

## 重新生成 Mermaid 后的理解

- `雅克科技(002409)` 是 2026-06-10 最新日报的最终观察对象，明日执行对象为空。
- `金安国纪(002636)` 是跨线过程候选，2026-06-11 走强只能证明过程候选池捕捉到强势扩散，不能倒算成最终对象命中。
- `双星新材(002585)` 是候选观察补充，2026-06-11 走弱必须进入失败样本。
- `中船特气(688146)` 是历史和过程证据，2026-06-11 继续强只能结算为历史跟踪有效，不能写成 2026-06-10 最新前台对象命中。
- 当前最合理判断是：输出身份漂移已被修复；候选池存在有效信号；但缺少按身份层级结算的次日归因表，所以现在还不能区分稳定能力和样本噪声。

## Contract: `next_day_attribution.v1`

```python
{
    "schema_version": "next_day_attribution.v1",
    "report_date": "YYYY-MM-DD",
    "review_date": "YYYY-MM-DD",
    "source_name": "str",
    "source_quote_time": "YYYY-MM-DD HH:MM:SS | None",
    "report_final_action": {
        "position_plan_pct": 0,
        "new_entry_target": None,
        "watch_target": {"code": "002409", "name": "雅克科技"},
    },
    "rows": [
        {
            "code": "002409",
            "name": "雅克科技",
            "identity_layer": "final_observation | execution_target | process_crossline | process_observation | historical_evidence | excluded",
            "source_bucket": "final_target_resolution | extreme_conviction_list | crossline_observation_stocks | historical_review | candidates",
            "report_role_text": "str",
            "participation_plan_pct": 0,
            "execution_qualification": "qualified | not_qualified | observation_only | incomplete",
            "planned_window": "09:50-10:10 | no_trade | unknown",
            "next_day_return_pct": "float | None",
            "next_day_high_pct": "float | None",
            "next_day_low_pct": "float | None",
            "close_status": "limit_up | strong | weak | failed | unknown",
            "counting_bucket": "final_observation_hit | execution_hit | process_candidate_hit | process_candidate_miss | historical_followup | excluded_not_counted",
            "attribution_summary": "str",
            "missing_fields": ["str"],
        }
    ],
    "summary": {
        "execution_hit_count": 0,
        "final_observation_hit_count": 1,
        "process_candidate_hit_count": 1,
        "process_candidate_miss_count": 1,
        "historical_followup_count": 1,
        "not_counted_as_execution_reason": "报告没有明日执行对象",
    },
}
```

## Contracts

1. 每个进入次日核验的标的必须先绑定 `identity_layer`，再绑定 `counting_bucket`。
2. `execution_target` 只能来自最终对象解析允许的新参与对象；报告无明日执行对象时，`execution_hit_count` 必须为 0。
3. `final_observation` 可以记录“最终观察层命中”，但不能自动升级为“执行命中”。
4. `process_crossline` 和 `process_observation` 必须同时记录成功与失败样本；不能只展示涨幅好的过程候选。
5. `historical_evidence` 必须单独结算为历史跟踪，不参与当日报告最终对象命中率。
6. 次日行情必须带来源和核验日期；缺失时该行保持 `unknown` 或 `missing_fields`，不能用无日期数据补齐历史归因。
7. 报告渲染次日归因时，必须同时输出“按身份层级的结论”和“不能算作执行命中的原因”。
8. 汇总统计必须明确分母：最终观察对象数、过程候选数、历史证据数分别统计，不允许混成单一胜率。

## Acceptance Criteria

- AC-R1-1: 给定 2026-06-10 日报最终对象为雅克科技且明日执行对象为空，生成次日归因时，雅克科技进入 `final_observation_hit`，`execution_hit_count` 仍为 0。
- AC-R1-2: 给定金安国纪来自跨线过程候选且次日上涨，生成次日归因时，金安国纪进入 `process_candidate_hit`，不计入最终对象命中。
- AC-R1-3: 给定双星新材来自候选观察补充且次日走弱，生成次日归因时，双星新材进入 `process_candidate_miss`。
- AC-R1-4: 给定中船特气只属于历史和过程证据，生成次日归因时，中船特气进入 `historical_followup`，不计入 2026-06-10 最新最终对象命中。
- AC-R2-1: 给定一份 0% 或仅观察报告，即使次日观察对象涨停，也不能输出执行命中。
- AC-R2-2: 给定行情事实没有 `review_date` 或来源时间，归因行必须标记缺失，不能进入成功或失败分母。
- AC-R3-1: 报告或 Mermaid 归因页必须展示最终观察、过程候选、历史证据三类分层，不只展示涨幅排行。
- AC-R3-2: 如果归因页把过程候选写成最终对象，验收检查必须失败。

## Verification

- 规格检查：确认 `reports/2026-06-10_次日归因闭环_mermaid.html` 能打开并渲染 Mermaid 图。
- 文案检查：新增 spec 和 HTML 不出现项目禁用的旧工程口径。
- 后续实现验证建议：
  - `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_decision_statistics tests.test_report_acceptance_audit`
  - 新增 `tests.test_next_day_attribution` 覆盖雅克科技、金安国纪、双星新材、中船特气四个身份样本。
  - 对 2026-06-10 日报运行一致性检查，并确认归因表不会改变原日报的明日执行对象。

## Delivery Slices

| Slice | 交付物 | 完成标准 |
|---|---|---|
| S1 | 归因版 Mermaid HTML | 图里能看出四个标的的不同身份和不同结算桶 |
| S2 | `next_day_attribution.v1` 数据契约 | 字段能表达报告身份、次日表现、结算桶和缺失事实 |
| S3 | 报告渲染 | 日报展示次日归因表，但不改写原始明日动作 |
| S4 | 验收检查 | 过程候选误写成最终对象、0% 报告误算执行命中时检查失败 |

## Execution Notes

- 已生成并修复 Mermaid 页面：`reports/2026-06-10_次日归因闭环_mermaid.html`。Mermaid 源码不再包含 raw `<br/>`，避免本地浏览器提前解析图内文本。
- 已新增 `scripts/report/next_day_attribution.py`，提供 `next_day_attribution.v1` 构建、渲染和包级审计。
- 已接入 `scripts/report/runtime.py`：只有 `data["next_day_attribution"]` 或 `market_research_snapshot["next_day_attribution"]` 存在时才渲染“次日归因闭环”章节，不自动抓取实时行情，不改变原日报明日动作。
- 已增强 `scripts/report/report_acceptance_audit.py`：出现次日归因章节时，过程候选误算为最终/执行命中、历史证据误算为当前命中、0%或仅观察报告误算执行命中都会失败。
- 已新增 `tests/test_next_day_attribution.py` 和 `tests.test_report_runtime.NextDayAttributionRuntimeTest`，覆盖雅克科技、金安国纪、双星新材、中船特气四个身份样本。

## Verification Results

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_acceptance_audit tests.test_next_day_attribution tests.test_report_runtime.NextDayAttributionRuntimeTest`：126 tests OK。
- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/next_day_attribution.py scripts/report/runtime.py scripts/report/report_acceptance_audit.py tests/test_next_day_attribution.py tests/test_report_runtime.py`：通过。
- `.generated/venv-py314/bin/python3.14 scripts/report/report_acceptance_audit.py reports/2026-06-10_A股日报_完整版.md --json`：`passed=true`。
- HTML 静态检查：3 个 Mermaid 图块；无 raw `<br/>`；无保留类名 `final/process/history/miss`；用户可见禁用说法扫描为空。

## Open Questions

- 次日归因是只在第二天盘后生成，还是在下一份日报开头自动展示“昨日归因”。
- 历史回填先覆盖最近 5 个交易日，还是直接覆盖已有 42 份正式日报。
- 过程候选命中是否需要再拆成“同主线过程候选”和“跨线过程候选”两个分母。
