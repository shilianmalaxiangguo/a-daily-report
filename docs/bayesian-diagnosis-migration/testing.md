# Bayesian 路径诊断测试记录

## 测试环境

- 分支：`codex/bayesian-diagnosis-integration`
- 基线：`2089f735 docs(report): add bayesian diagnosis integration prd`
- Python：`/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14`

## 已通过的检查

### 1. 空白与差异检查

```bash
git diff --check
```

结果：通过，没有发现空白错误。

### 2. 相关单测

```bash
/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14 -m unittest \
  tests.test_bayesian_diagnosis \
  tests.test_sniper_target_derivation \
  tests.test_front_page_v2_renderer \
  tests.test_report_acceptance_audit \
  tests.test_report_runtime \
  tests.test_selection_workflow
```

结果：通过。

```text
Ran 544 tests in 8.523s
OK
```

### 3. 新增用户可见文案扫描

已扫描本次新增的用户可见文字，没有发现项目禁用工程口径。

### 4. 前页渲染测试差异复核

已复核 `tests/test_front_page_v2_renderer.py`，当前只新增一条 Bayesian 首页展示顺序测试，没有混入无关重排。

## 覆盖到的核心契约

| 契约 | 覆盖方式 |
|---|---|
| Bayesian 不能覆盖最终动作 | `tests/test_sniper_target_derivation.py`、`tests/test_report_runtime.py` |
| 50% 条件执行必须保留回到 0% 不参与 | `tests/test_bayesian_diagnosis.py` |
| 0% 不参与不能包装观察对象 | `tests/test_bayesian_diagnosis.py` |
| 来源日期缺失必须显式暴露 | `tests/test_bayesian_diagnosis.py`、`tests/test_report_acceptance_audit.py` |
| 反证会降低路径结论 | `tests/test_bayesian_diagnosis.py` |
| 首页路径诊断在最终结论之后 | `tests/test_front_page_v2_renderer.py` |
| 粗糙概率表达会被检查指出 | `tests/test_report_acceptance_audit.py` |
| 对象不一致必须显式展示 | `tests/test_report_acceptance_audit.py` |
| 0% 不参与仍保留路径复盘，但不渲染成最终对象路径图 | `tests/test_sniper_target_derivation.py`、`tests/test_report_runtime.py` |

## replay 尝试结果

尝试过以下日期的 replay：

- `2026-05-29`
- `2026-06-01`
- `2026-05-28`
- `2026-05-26`
- `2026-05-22`

结果：尚未得到完整样例日报。失败原因来自现有历史快照或数据缺口，例如缺少 `中证1000`、hot top50、价格带风格字段，或既有一致性检查未通过；没有发现这次 Bayesian 接入引入新的 Python 异常。

## 合并前建议人工确认

1. 找一个可完整 replay 的日期重新生成日报。
2. 看首页“路径诊断复盘”是否放在最终结论后方，且没有抢走最终动作位置。
3. 看附录完整路径是否能帮助复盘，而不是制造第二套结论。
4. 如出现来源日期缺失，确认它被如实展示，而不是被当成目标日期事实。
