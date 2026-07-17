# Implementation: 受控 Agent Memory Vault 试点

## Prerequisites

- 用户已确认独立源码、私有数据和 runtime 三目录布局。
- 三个目标目录在实施前均不存在。
- 当前日报仓库有大量既有未提交修改，本任务只编辑自己的 Trellis 任务目录。
- 所有 Python 命令使用固定 Python 3.14。

## Ordered Checklist

- [x] I1: 完成 PRD、研究、设计与实施清单，并检查任务范围与既有项目 `vault/` 边界。
- [x] I2: clone 外部仓库到独立源码目录，记录 upstream commit，创建 `codex/controlled-memory-pilot` 本地分支。
- [x] I3: 先补 CLI 失败测试，再实现默认 Top 3、默认无搜索日志、closeout 默认 dry-run 和显式提交兼容。
- [x] I4: 先补策略失败测试，再实现配置化记忆类型、必填字段、状态、复核日期、来源路径和敏感写入检查。
- [x] I5: 补检索测试并实现到复核日期内容默认排除及显式包含参数。
- [x] I6: 更新公开示例配置、安装文件清单和受控试点文档，保持无私人路径的默认模板。
- [x] I7: 使用固定 Python 3.14 运行外部仓库全部基础测试与新增测试，修正本任务引入的问题。
- [x] I8: 创建私有 Markdown、runtime 与本机 TOML/策略文件；禁用向量、Hook、周期任务和自动提交。
- [x] I9: 初始化 SQLite，写入最小跨项目指针与架构决定，运行 check、索引和固定检索验收。
- [x] I10: 验证 runtime 安装指纹、私有路径隔离、默认 dry-run、默认无日志和停用独立性。
- [x] I11: 运行当前日报项目 Wiki、正式决定与 replay 的最窄测试，确认日报仓库运行行为不变。
- [x] I12: 执行 Trellis 检查和一轮只读提交前审计，记录修改文件、验证结果和剩余问题；提交前向用户确认。
- [x] I13: 按用户补充确认建立两个独立 private 远端，分别推送受控源码和私有 Markdown，并将日报任务文档推送到既有私有远端。

## Validation Commands

- `/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14 -m unittest discover -s tests -v`
- `/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/.generated/venv-py314/bin/python3.14 scripts/agent_memory_check.py --skip-state-db`
- `/Users/chaixixi/.config/agent-memory/scripts/install_runtime.py --config-root /Users/chaixixi/.config/agent-memory --verify --json`，由固定 Python 3.14 调用。
- 使用固定 Python 3.14 运行 `memoryctl doctor --json`，验证私有 Markdown 的 Git 基线与远端备份。
- 使用 runtime TOML 初始化和扫描私有索引，再执行默认 Top 3、过期排除、范围隔离与冲突样本查询。
- `.generated/venv-py314/bin/python3.14 scripts/knowledge/llm_wiki_lint.py`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_llm_wiki_manifest tests.test_llm_wiki_router`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_report_runtime tests.test_report_replay`
- `git diff --check`

## Risk And Rollback Points

- I2 前确认目标源码目录不存在；存在时停止，不能覆盖。
- I8 前再次确认私有数据和 runtime 目录不存在；存在时停止，不能覆盖。
- runtime 安装器后续会覆盖 hash 不同的脚本，因此本任务只在空目录首次安装一次。
- 不运行 `memoryctl closeout --commit`，不启用自动提交或自动推送；仅在用户明确确认后执行人工提交和推送。
- 私有 Vault 只跟踪 Markdown 与 `.gitignore`；runtime、SQLite、日志、报告和模型继续保存在 Git 之外。
- 不修改日报仓库现有 `vault/`、Wiki、scripts、tests、reports 或 snapshots。

## Review Checkpoints

- I1 后：PRD 与设计是否保持单一事实来源，是否遗漏既有项目 `vault/`。
- I6 后：外部 fork 修改是否只针对当前风险，没有引入向量、Hook 或新服务。
- I9 后：私有内容是否只有短指针和架构决定，没有历史正文迁移。
- I11 后：日报 manifest/trace、正式决定与 replay 是否保持原行为。
- I12：按仓库要求使用只读子代理做提交前审计，主代理点验关键出处。
- I13：三个仓库是否分别跟踪自己的远端，私有 Vault 是否没有派生文件进入 Git。
