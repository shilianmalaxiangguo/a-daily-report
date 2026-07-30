# Design: 日报 PostgreSQL replay 与紧凑快照迁移

## Scope And Boundaries

目标结构是“PostgreSQL 正式事实 + 专用紧凑投影 + 旧 JSON 兼容 reader”。迁移分四段推进，本轮先完成阻止异常膨胀的写入保护，不在未验收 replay 前删除旧入口。

### 本轮实现边界

- 切断 `execution_stage_context` 对完整 `data` 的引用，并移除可调用对象。
- 序列化器按当前递归路径识别循环引用，保留合法共享引用的正常内容。
- 快照通过同目录临时文件写入，超过 64MiB 立即停止并清理临时文件，成功后原子替换目标。
- 主日报入口记录正式/replay 快照成功与失败的路径、模式、字节数和尺寸限制结果；备用编排器继续复用同一尺寸保护，但其结构化观察迁移不在本阶段冒充已完成。
- 记录后续 PostgreSQL replay 和消费者迁移设计，不在本轮修改数据库结构。

### 本轮不改变

- replay 仍可读取旧官方 JSON。
- 正式历史冻结策略不变。
- 报告判断、选股、仓位和展示顺序不变。
- 不删除任何现有文件。

## Contracts / Data Flow

### 当前数据流

```text
实时/数据库事实
  -> 完整 data
  -> PostgreSQL 紧凑事实
  -> Markdown/Bear
  -> 完整 JSON
  -> replay、snap-ui、发布器、导出器
```

异常路径：

```text
data
  -> execution_stage_context["data"]
  -> data["execution_stage_context"]
  -> 序列化重复展开至 50 层
```

### 目标数据流

```text
目标日期来源事实
  -> PostgreSQL 结构化事实与紧凑字段
  -> PostgreSQL replay source adapter
  -> replay 合同
  -> Markdown/Bear/验收

PostgreSQL
  -> snap-ui 专用查询投影
  -> 发布器公开摘要投影

过渡期
  -> 小于等于 64MiB 的紧凑灾备快照

旧完整 JSON
  -> 一次性导入或显式手工修复
```

### 循环引用契约

- 只把“当前递归路径中再次出现同一对象”视为循环引用。
- 同一对象在兄弟字段中重复出现但不形成循环时，两个字段都正常序列化，避免丢失合法共享事实。
- 循环位置写为稳定占位文本，不再向下展开。
- 运行期执行上下文保存前移除 `data` 和可调用对象；候选、判断、阶段输出和来源日期继续保留。

### 快照写入契约

- 最大字节数为 64MiB，以 UTF-8 实际写入字节计数。
- 写入同目录唯一临时文件；只有完整 JSON 写入、刷新和大小检查全部成功后才用 `os.replace()` 更新目标。
- 超限或异常时删除临时文件；已有目标文件保持原样。
- 正式文件已冻结时，仍只写 replay 路径，沿用现有保护行为。

### PostgreSQL replay source adapter

后续 S2 保留现有 `load_data_snapshot(target_date) -> (data, supplementary)` 的调用形状，但把生产默认实现替换为目标日期 PostgreSQL adapter：

1. 加载通用紧凑事实与现有结构化表。
2. 补齐冻结知识引用、补充观察和来源日期。
3. 生成 replay 基线对象。
4. 对关键事实运行完整性检查。
5. 只有显式兼容模式才读取旧官方 JSON。

这样可以保留大量参数注入测试，不要求一次性删除旧 reader。

## Compatibility / Migration

### S1：立即保护

- 新文件不再因已知循环膨胀。
- 64MiB 限制阻止未知结构继续写出 GB 级文件。
- 旧文件保持原样可读。

### S2：PostgreSQL replay

- 先补“数据库载荷 → replay 合同 → Markdown/Bear”测试。
- 冻结知识引用和补充观察优先复用现有紧凑字段；只有查询与约束证明不适合时才提出表结构变更，并在变更前再次确认。
- PostgreSQL-only replay 禁止实时刷新和历史 Markdown 补值。

### S3：消费者迁移

- 判断复盘与前瞻复盘直接读 PostgreSQL。
- snap-ui 使用日期列表、主线序列、观察池、热区和个股结构等专用查询，不暴露内部宽投影。
- 发布器读取公开白名单投影，不加载完整日报对象。

### S4：停止新增完整 JSON

- 至少选取多个交易日完成双路径逐字段验收和恢复演练。
- 停止新的完整 JSON 写入，但保留旧 reader 和旧档案。
- 旧文件清理先输出预演清单；删除必须另行确认。

## Tradeoffs

- 64MiB 过渡快照仍是重复存储，但能立即限制风险，并为 PostgreSQL replay 迁移保留恢复余地。
- 只在序列化器处理循环而不清理运行期上下文，会留下大量无用函数标记；因此两处都修。
- 只清理运行期上下文而不增加通用循环识别，其他调用者仍可制造循环；因此序列化边界也要保护。
- 立即删除完整 JSON 可最快释放空间，但当前会中断 replay、snap-ui 和发布器，不满足可验证迁移要求。
- 将所有原始载荷塞入 PostgreSQL 会把 1.3GB 文件问题转移到数据库；目标只保存 replay 必需的紧凑事实和专用结构化数据。

## Rollback / Roll-forward

- S1 如误删业务字段，只回退执行上下文清理，保留循环识别和原子尺寸保护；已有文件不受影响。
- 快照超限时不放宽到 GB 级，先定位新增字段并决定是否进入 PostgreSQL、独立缓存或不持久化。
- S2/S3 发现字段不一致时继续保留旧 JSON 兼容路径，修正 PostgreSQL 投影后重新验收。
- 已写入的 PostgreSQL 事实采用向前修正；不在本任务中执行破坏性历史回滚。
