# Research: precommit sector-first quant Brooks spec review

- Query: 提交前审阅“板块先行 + A股量化参与导致高潮/冰点两重天 + Brooks价格行为本地化”判断应如何落入 spec。
- Scope: mixed
- Date: 2026-06-13

## Findings

### 结论

最应该落到 `.trellis/spec/backend/daily-report-decision-loop.md`。

理由：

- 该判断影响日报最终执行对象、前台同源展示、缺失数据停止生成、0%/50%/100%仓位、历史 replay 边界和事后复盘归因，正属于 daily report decision loop 的范围。
- 现有 spec 已经有 `selection_workflow.derivation_contract = "sector_first_strict.v1"`、`selection_workflow.final` 作为唯一最终执行对象、0% 结果下过程候选只能观察、关键数据缺失停止生成等契约，见 `.trellis/spec/backend/daily-report-decision-loop.md:198`、`.trellis/spec/backend/daily-report-decision-loop.md:199`、`.trellis/spec/backend/daily-report-decision-loop.md:200`、`.trellis/spec/backend/daily-report-decision-loop.md:202`。
- `.trellis/spec/backend/quality-guidelines.md` 更适合补充候选质量、板块锚和追踪图的局部规则，不应承接这条日报主链路判断。

### Files Found

- `.trellis/tasks/06-11-daily-report-market-sector-leader-derivation/prd.md` - 当前任务要求从市场、板块、龙头、价格行为到执行资格逐层推导，并禁止旧式涨停/T字板入口。
- `.trellis/tasks/06-11-daily-report-market-sector-leader-derivation/design.md` - 已定义 `derivation_contract = "sector_first_strict.v1"`、N0-N9 数据流、候选入口、线路优先级和缺失数据处理。
- `.trellis/spec/backend/daily-report-decision-loop.md` - 最匹配的 spec 文件，已经承载日报执行对象、计划参与、缺失字段、回放边界和验证矩阵。
- `wiki/板块补充/板块中枢与主线延续.md` - 交易思想来源，明确量化环境下板块节奏优先、板块先铺再筛核心、窄池子进攻、量化仍在/离场、抱团环境等字段。
- `wiki/交易思想/布鲁克斯价格行为趋势.md` - 交易思想来源，明确 A股量价本地化、趋势区间谱系、K线收盘质量、突破失败测试、二次入场、迟到入场和交易者等式。
- `scripts/report/selection_workflow.py` - 当前实现已有 `DERIVATION_CONTRACT = "sector_first_strict.v1"`、`market_layer`、`sector_layer`、`leader_layer`、Brooks 判断、缺失字段停止提示和最终对象字段。
- `tests/test_selection_workflow.py` - 当前测试已覆盖 derivation contract、板块层字段、Brooks 量价判断、缺失关键数据、仓位归一和旧入口降权。

### Code Patterns

- `scripts/report/selection_workflow.py:5` 定义 `DERIVATION_CONTRACT = "sector_first_strict.v1"`，spec 应继续约束该契约，不新增平行契约名。
- `scripts/report/selection_workflow.py:726` 至 `scripts/report/selection_workflow.py:741` 已构造 `market_layer`、`sector_layer`、`leader_layer`，spec 应字段化这些层，而不是只写自然语言规则。
- `scripts/report/selection_workflow.py:713` 至 `scripts/report/selection_workflow.py:716` 和 `scripts/report/selection_workflow.py:746` 至 `scripts/report/selection_workflow.py:748` 已把缺失字段写入失败状态，spec 应要求关键字段缺失时停止生成。
- `scripts/report/selection_workflow.py:753` 至 `scripts/report/selection_workflow.py:758` 已汇总 Brooks price-action 结果，spec 应要求价量确认不是单一成交量判断。
- `scripts/report/selection_workflow.py:823` 至 `scripts/report/selection_workflow.py:843` 输出 `derivation_contract`、分层结果和 `final.position_pct`，spec 应要求所有展示层只消费这一份结果。
- `tests/test_selection_workflow.py:48`、`tests/test_selection_workflow.py:78` 至 `tests/test_selection_workflow.py:86` 已断言 contract、市场层、板块层、龙头层和 N6/N7 传递字段。
- `tests/test_selection_workflow.py:284` 至 `tests/test_selection_workflow.py:309` 已断言“成交量不能单独生成参与资格”。
- `tests/test_selection_workflow.py:313` 至 `tests/test_selection_workflow.py:338` 已断言“资金表态未被价格接受”只能作为过程证据。

### Related Specs

- `.trellis/spec/backend/daily-report-decision-loop.md:199` 要求 `selection_workflow.final` 是最终执行对象唯一来源。
- `.trellis/spec/backend/daily-report-decision-loop.md:200` 要求 0% 或空最终结果下，过程候选全层改为观察/过程回放语义。
- `.trellis/spec/backend/daily-report-decision-loop.md:202` 要求 market、sector、leader、price-action、account-execution 缺失进入停止生成集合。
- `.trellis/spec/backend/daily-report-decision-loop.md:227` 至 `.trellis/spec/backend/daily-report-decision-loop.md:243` 已有验证矩阵，可在此追加更细的 sector-first + Brooks 本地化行。
- `.trellis/spec/backend/daily-report-decision-loop.md:267` 至 `.trellis/spec/backend/daily-report-decision-loop.md:287` 已有测试要求位置，适合追加本任务测试名称。

### External References

- 外部链接由主线程摘要读取：页面标题为“AI复活已故名人讨论与投资方法论在A股适用性综合报告”。
- 可吸收观点：Brooks 价格行为有趋势、纪律和交易数学价值；A股存在量化高频、震荡频繁、政策扰动、弱有效、散户情绪和风格剧烈切换，因此纯价格行为必须本地化。
- 不应吸收为硬编码事实：不写入固定量化占比、不写入某个市场参与者比例、不把外部文章具体结论变成永久阈值。

### 必须包含的可执行字段

建议在 `.trellis/spec/backend/daily-report-decision-loop.md` 新增或补强一个场景：`Selection Workflow Sector-First And A-Share Price-Action Localization`。

最小可执行字段：

```python
{
    "schema_version": "selection_workflow.v1",
    "derivation_contract": "sector_first_strict.v1",
    "source_dates": {
        "report_date": "YYYY-MM-DD",
        "snapshot_date": "YYYY-MM-DD | None",
        "sector_source_date": "YYYY-MM-DD | None",
        "price_source_date": "YYYY-MM-DD | None"
    },
    "market_layer": {
        "market_atmosphere": "str",
        "profit_effect": "str",
        "turnover_quality": "str",
        "risk_preference": "str",
        "narrow_pool_attack": "bool | str | None",
        "quant_bifurcation": "bool | str | None",
        "allow_sector_diagnosis": "bool",
        "missing_fields": ["str"]
    },
    "sector_layer": {
        "selected_direction": "str | None",
        "sector_path_selected": "bool",
        "sector_trend": "str",
        "sector_fermentation": "str",
        "sector_emotion": "str",
        "turnover_expansion": "str",
        "backrow_acceptance": "str",
        "second_wave_high_group": "str | bool | None",
        "competition_line_state": "str | None",
        "quant_still_present_evidence": ["str"],
        "quant_exit_evidence": ["str"]
    },
    "emotion_line_layer": {
        "enabled": "bool",
        "source": "market_atmosphere | scarcity_recognition | capacity | public_participation",
        "leader": {"code": "str | None", "name": "str | None"},
        "capacity_evidence": ["str"],
        "public_participation_evidence": ["str"],
        "divergence_acceptance": "str | None",
        "missing_fields": ["str"]
    },
    "leader_layer": {
        "leader_source": "sector_fermentation | emotion_line | pending",
        "leader": {"code": "str | None", "name": "str | None"},
        "market_selected_evidence": ["str"],
        "why_not_sector_anchor": "str | None",
        "why_not_backrow_or_old_leader": "str | None"
    },
    "candidate_lifecycle": [
        {
            "candidate": {"code": "str", "name": "str"},
            "source_path": "sector_derived | emotion_line | holding_risk | manual_observation | legacy_process",
            "new_entry_qualified": "bool",
            "role": "new_entry | risk_handling | observation | process_evidence",
            "entry_basis": ["str"],
            "blocking_reasons": ["str"]
        }
    ],
    "price_action_layer": {
        "a_share_volume_localization": "str",
        "volume_as_capital_expression": "str",
        "volume_price_quadrant": "accepted | rejected | pending | risk_first",
        "trend_range_spectrum": "strong_trend | trend | broad_channel | trading_range | tight_range | unknown",
        "bar_close_quality": "strong_close | mid_close | weak_close | unknown",
        "follow_through_confirmation": "confirmed | missing | failed | pending",
        "breakout_failure_test": "passed | failed | pending | not_applicable",
        "second_entry_confirmation": "confirmed | missing | not_required | pending",
        "late_entry_no_chase": "bool | str",
        "trader_equation": {
            "success_probability": "str | float | None",
            "target_space": "str | float | None",
            "failure_loss": "str | float | None",
            "position_damage": "str | float | None"
        },
        "signal_not_qualification": "bool"
    },
    "final": {
        "execution_object": {"code": "str", "name": "str"} | {},
        "position_pct": 0 | 50 | 100,
        "action_text": "str",
        "failure_conditions": ["str"]
    },
    "missing_fields": ["str"]
}
```

字段设计要点：

- `quant_bifurcation` / `quant_still_present_evidence` 只记录“高潮/冰点两重天、窄池子、成交集中、后排承接、竞争线掉队”等可观察现象，不记录硬编码量化资金占比。
- `price_action_layer` 必须把成交量放在“资金表态”位置，把价格接受放在最终确认位置。
- `candidate_lifecycle.source_path` 必须区分新仓候选、持仓风险处理、手动观察和旧过程证据，防止后两者绕过板块推导。
- `source_dates` / `missing_fields` 必须保留，避免 replay 把当前事实混进历史日期。

### 必须包含的验证矩阵

建议追加以下矩阵行：

| Situation | Required Handling |
|---|---|
| 指数上涨但上涨家数弱、成交集中在少数方向 | `market_layer.narrow_pool_attack` 记录窄池子进攻；不得把指数上涨写成全市场参与质量提高 |
| 板块成交占比扩张、板块宽度扩散、核心分歧后仍承接 | `sector_layer.sector_path_selected=True`，并记录 `quant_still_present_evidence` |
| 板块成交占比回落、后排掉队、核心跌回 VWAP 或关键均线 | 记录 `quant_exit_evidence`，降低或取消新仓参与资格 |
| 单只涨停/T字板/一字板但无板块扩散、二波创新高群和后排承接 | 只能进入过程证据或观察，`new_entry_qualified=False` |
| 板块先铺后，弹性载体持续新高、核心锚横住或跟随、后排仍承接 | 可进入龙头推导，但仍需 price-action 和账户执行确认 |
| 普跌或窄池子下出现市场总龙 | 可启用 `emotion_line_layer`，但必须有稀缺辨识度、成交容量、大众可参与性和分歧承接；缺任一关键项停止或降为缺失 |
| 市场情绪线和板块主线都强但指向不同对象 | 输出 PK 对照；价格行为和账户条件未分胜负时不得给 100% |
| 放量上涨、强收盘、板块同步、回踩不破 | 可进入最终对照；仍需账户、时间窗口、失效线和交易者等式 |
| 放量冲高回落、长上影或弱收盘 | 写为“资金表态未被价格接受”；不得生成参与资格 |
| 强趋势中第一次逆势 K 线 | 默认写为回调/观察；不得直接写成趋势反转 |
| 错过早期买点且价格远离失效线 | `late_entry_no_chase=True`，最终只能小仓上限或观察；不得补偿式追高 |
| 任何 market / sector / emotion-line / leader / price-action / account-execution 关键字段缺失 | 停止生成并列出缺失字段；不得用热榜、涨停池、历史龙头记忆回退生成新仓结论 |
| 历史 replay 缺少同日板块或价格事实 | 保留缺失并停止相关结论；不得调用当前数据填充目标日期 |

### 避免写入 spec 的误区

- 不写硬编码量化资金占比、固定高频参与比例或无法从本仓库事实验证的市场结构数字。
- 不把“量化参与导致两重天”写成单一因果定论；应字段化为窄池子、成交集中、扩散/掉队、核心承接、竞争线状态。
- 不把 Brooks 价格行为写成独立选股系统；它只负责价格接受、失败测试、二次确认和交易者等式，不能替代板块、主线、账户和时间窗口。
- 不把成交量、涨停、连板、T字板、一字板、热榜、题材标签或旧龙头记忆恢复为新仓入口。
- 不把所有字段叠成“完美股票”巨型筛选器；spec 应要求按处境选择证据，而不是要求所有字段同时满足。
- 不把 wiki 表达原样搬进用户可见工程输出；日报正文仍需遵守 `wiki/交易思想/日报术语契约.md`。
- 不把外部文章的具体案例、政策判断或当前市场描述写成永久规则；只能吸收为验证字段和反例。

### 建议测试断言名称

优先补在 `tests/test_selection_workflow.py`：

- `test_index_strength_with_weak_breadth_sets_narrow_pool_attack_without_market_wide_upgrade`
- `test_sector_turnover_expansion_and_backrow_acceptance_marks_sector_path_selected`
- `test_single_limit_up_without_sector_diffusion_remains_process_evidence`
- `test_sector_first_spread_then_screens_capacity_core_as_leader_candidate`
- `test_quant_exit_evidence_blocks_new_entry_when_backrow_fails_and_core_loses_vwap`
- `test_market_emotion_line_requires_capacity_public_participation_and_divergence_acceptance`
- `test_emotion_line_and_sector_mainline_conflict_caps_position_below_full`
- `test_a_share_volume_accepted_requires_strong_close_follow_through_and_sector_sync`
- `test_volume_rejection_records_capital_expression_without_participation`
- `test_first_countertrend_bar_in_strong_trend_is_observation_not_reversal`
- `test_late_entry_far_from_invalid_price_sets_no_chase_and_zero_position`
- `test_missing_sector_first_critical_inputs_stop_before_report_artifacts`

跨渲染/审计层可补：

- `tests.test_front_page_v2_renderer.FrontPageV2RendererTest.test_sector_first_final_object_is_only_execution_source`
- `tests.test_daily_report_render.DailyReportRenderTest.test_zero_position_sector_first_process_rows_are_observation_only`
- `tests.test_report_acceptance_audit.ReportAcceptanceAuditTest.test_audit_flags_sector_first_participation_text_under_zero_position`

## Caveats / Not Found

- 未重新打开外部链接；外部观点只使用主线程已提供摘要。
- `task.py current --source` 返回无活动任务；本次按用户明确给出的任务目录写入研究文件。
- 未编辑 code、spec 或 wiki；只新增本研究文件。
- 当前审阅未验证主线程未提交代码的最终 diff，因此测试名称是提交前补断言建议，不代表现有代码一定已全部覆盖。
