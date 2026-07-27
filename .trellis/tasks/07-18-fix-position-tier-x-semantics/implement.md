# Implementation: 修复仓位档与1x/2x语义串位

## Prerequisites

- 用户已确认 `0=0%`、`1x=50%/B1`、`2x=100%/B1+B2`。
- 当前任务在独立 Trellis 目录中推进，不改变 07-17 选择性暂存。
- 修改混合文件前读取当前工作区版本，并按函数块核对差异。

## Ordered Checklist

- [x] I1: 新增仓位换算契约单测，覆盖 0/1x/2x 与 0/50/100 双向映射。
- [x] I2: 把前日报默认1x的三个错误100%测试改成失败回归，并增加显式真实100%保持2x的反例。
- [x] I3: 把 runtime 50%→满仓测试改成“保持1x/50%”，增加 Markdown/stdout/Bear 端到端断言。
- [x] I4: 实现纯仓位契约并接入 position_context 的默认旧仓归一。
- [x] I5: 产出 `position_tier_exposure.v2`，按旧仓/新仓每腿汇总到最大2x/100%，保留 v1 读取兼容。
- [x] I6: 删除 runtime 的仓位字符串升档，保留独立风险文字净化；同步首页与持仓策略读取 v2 数值字段。
- [x] I7: 修正验收检查，拒绝50%/满仓、1x/100%、2x/200%组合并接受正确三档。
- [x] I8: 更新 Wiki、LLM 上下文、知识路由和 backend spec，保留旧关键词检索兼容。
- [x] I9: 跑定向测试，再跑所有受影响模块；逐字段比较最终对象、仓位数值、窗口和取消条件。
- [x] I10: 修复后由子代理完成提交前范围、逻辑、测试和用户可见文案复核；审计发现的非法中间比例升档、旧仓小数越档、显式缓存档绕过、盘前复核宽松消费和两层缺仓位默认半仓均已修复并复核。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_position_tier_contract tests.test_position_action_semantics`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_two_layer_decision_payload tests.test_report_acceptance_audit`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output tests.test_llm_wiki_context tests.test_llm_wiki_router`
- `.generated/venv-py314/bin/python3.14 -m py_compile scripts/report/position_tier_contract.py scripts/report/position_context.py scripts/report/runtime.py scripts/report/front_page_v2_renderer.py scripts/report/report_acceptance_audit.py`
- `git diff --check`

## Risk And Rollback Points

- `scripts/report/runtime.py`、LLM Wiki 文件和相关测试为 staged/unstaged 混合文件，只修改明确函数块，不整文件暂存。
- 前日报继承影响 replay 和持仓策略，必须同时覆盖坏100修复与显式真实100保留。
- 暴露 v2 只替代仓位解释，不改变资本优先级、最终对象或旧仓动作类别。
- 任何最终对象、交易窗口或取消条件变化都视为越界。

## Review Checkpoints

- 测试先行后确认失败原因确为旧语义，而非夹具缺失。
- 生产实现后先跑定向测试，再扩展到渲染、入口和知识链。
- 最终对 `git diff` 做函数块级范围审计，确认 07-17 暂存区未改变。

## Verification Result

- 2026-07-19：原定 3 组命令共运行 1029 项测试，全部通过。
- `tests.test_position_tier_contract tests.test_position_action_semantics`：32 项通过。
- `tests.test_report_runtime`：342 项通过。
- `tests.test_front_page_v2_renderer tests.test_position_strategy_report tests.test_two_layer_decision_payload tests.test_report_acceptance_audit`：434 项通过。
- `tests.test_daily_report_markdown_html tests.test_daily_report_entry_html_output tests.test_llm_wiki_context tests.test_llm_wiki_router`：221 项通过。
- `tests.test_elimination_tournament` 与 `tests.test_two_layer_decision_payload` 完整模块各 45 项通过；新增回归确认非法盘前仓位不会进入执行窗口、缺仓位对象不会默认取得 B1。
- Python 3.14 `py_compile`、工作区 `git diff --check` 和暂存区 `git diff --cached --check` 通过。
- 三个 v2 场景额外验证首页保留原定执行对象、`participation_window`、执行条件和取消条件，只改当前新增仓位解释。

## Audit Result

- 修复前提交审计已完成：仓位数据流、测试缺口、LLM Wiki 字段映射和测试 stdout 来源四路审计均返回结论，确认问题已逐项修复。
- 修复后独立审计确认三种 v2 流程、最终对象、窗口和条件保持正确，并发现同源边界缺陷：非法中间比例升档、旧仓小数越档、显式旧计划信任缓存、盘前复核宽松消费和两层缺仓位默认半仓。均已补测试并修复。
- 最终独立复核确认合法 `50/100` 保留原对象、窗口和条件，非法/缺失计划不会回退成另一只股票；实际持仓 `40%-60%` 仍只在账户事实层归入 1x。
- 仓位上限复核确认 `60/75` 只会把已有合法 `100` 计划降到 `50`，不能从 `0` 或非法基础计划生成 B1；月度上限只展示、不生成对象，总暴露不超过 `100%`。无剩余实现 finding。
