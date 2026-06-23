# Daily Report Project

## 目标

让 A 股日报稳定回答：今天市场发生了什么、明天是否可做、唯一对象或观察对象是什么、什么条件出现后不参与。

## 当前状态

- `wiki/` 已承担稳定交易知识和日报口径。
- `.trellis/` 已承担开发任务、规格和检查记录。
- `reports/` 与 `snapshots/` 承担日报产物和回放事实。
- `vault/` 从今天开始承担跨会话工作记忆索引。

## 关键文件

- `AGENTS.md`：仓库协作规则。
- `SKILL.md`：日报 skill 入口。
- `wiki/README.md`：LLM Wiki 路由入口。
- `wiki/运行契约/LLM Wiki维护与路由契约.md`：知识写入与路由边界。
- `.trellis/workspace/`：开发过程记忆。

## 最近决策

- 2026-06-23：新增 `vault/`，采用 `TODO.md`、`people/`、`projects/`、`agent/`、`notes/` 的长期记忆结构。
- 2026-06-23：`vault/` 只做工作记忆索引，不替代 `wiki/` 的稳定交易知识，也不替代 `.trellis/` 的开发任务管理。

## 风险与未确认点

- 首批内容需要人工筛选，不能把所有对话流水直接搬进 vault。
- vault 笔记如果长期不升级到 `wiki/` 或 `.trellis/`，会变成新的信息噪音。

## 下一步

- 从最近几次日报修复和复盘中挑选 3 到 5 条真正需要长期记住的内容。
- 对每条内容判断去向：留在 `vault/notes/`、升级到 `wiki/`，或升级到 `.trellis/tasks/`。
