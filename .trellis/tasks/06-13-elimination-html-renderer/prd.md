# 淘汰赛HTML渲染器

状态：✅ 已完成（未提交）

## Goal

为淘汰赛 payload 提供静态 HTML 渲染器，让用户能直观看到每一层输入、淘汰、剩余、理由和最终唯一动作。

## User Story

- **角色**：日报使用者。
- **场景**：打开日报 companion HTML，复核选股决策链。
- **目标**：看清每只股票在哪层被保留或淘汰，以及最终为什么只有一个动作。
- **成功标准**：HTML 不产生新的明日标的，只解释 payload 中的唯一最终动作和分层淘汰证据。

### 用户旅程

1. 用户打开淘汰赛 HTML。
2. 用户按层阅读板块层到最终收口层。
3. 用户定位某只股票，看到淘汰理由或保留依据。

## What I Already Know

- 父任务要求 HTML 为决策审计 artifact，不是营销页。
- HTML 必须避免多个并列明日标的。
- 颜色不能作为唯一信息来源。

## Requirements

- [x] R1: 渲染器接收淘汰赛 payload 并输出完整 HTML 字符串。
- [x] R2: HTML 包含六层标题、数量摘要、淘汰名单、剩余名单、理由列表。
- [x] R3: HTML 明确展示最终唯一动作，且只在最终收口层展示。
- [x] R4: HTML 对数据不足层显示缺失说明。
- [x] R5: 视觉结构适合桌面阅读，表格/列表紧凑清楚。

## Non-functional Requirements

### 性能
- 静态字符串渲染，不引入浏览器端框架。

### 安全
- 用户可见字段需要 HTML escape。

### 兼容性
- 可直接用浏览器打开本地 HTML 文件。

### 可访问性
- 标题层级清楚；表格含表头；颜色不作为唯一语义。

## Acceptance Criteria

- [x] AC-R1-1: 给定最小 payload，渲染器返回包含 `<!doctype html>` 的 HTML。
- [x] AC-R2-1: 给定六层 payload，HTML 中出现六个层级标题及数量摘要。
- [x] AC-R3-1: 非最终层不出现“明日唯一动作”。
- [x] AC-R4-1: 数据不足层显示缺失说明。
- [x] AC-R5-1: HTML escape 覆盖股票名、理由、板块等文本字段。

## Definition Of Done

- [x] Requirements 全部完成。
- [x] Acceptance Criteria 全部通过。
- [x] Focused tests 覆盖渲染结构、HTML escape 和最终动作唯一展示。
- [x] PRD 状态改为 `✅ 已完成` 并补充落地 commit。

## Out Of Scope

- 不接入日报生成命令。
- 不实现复杂交互或前端框架。
- 不引入远程资源。

## Technical Notes

### 参考来源
- `.trellis/tasks/06-13-sector-first-elimination-html/design.md`
- `.trellis/tasks/06-13-elimination-evidence-contract/prd.md`

### 影响区域
- `scripts/report/` 下新增或扩展 HTML renderer。
- `tests/` 下新增 focused tests。

## Verification

- `.generated/venv-py314/bin/python3.14 -m unittest <focused renderer tests>`
- `git diff --check`

## 落地结果

- 本轮未提交 commit。
- 代码：`scripts/report/elimination_tournament.py`。
- 测试：`tests/test_elimination_tournament.py`。
- 验证：`.generated/venv-py314/bin/python3.14 -m unittest tests.test_elimination_tournament` 通过，8 tests OK。
