# PSQL 驱动 HTML 日报设计

日期：2026-06-07

## 任务定级

按 `task-mode` 分流，本任务属于 Ultra。

理由：

- 涉及 PSQL 存储、日报生成主链路、HTML 阅读产物和后续实施拆分。
- 目标不是单纯换一个输出格式，而是把 HTML 日报建立在 PSQL 事实层之上。
- 需要先写中文规格，再按最小可验证步骤实施。

本文件只定义规格和后续任务分配，不进入代码实现。

## 目标

为 A 股日报新增 PSQL 驱动的 HTML 阅读产物。

核心目标：

1. 每个交易日日报都可以生成一个 HTML 阅读文件。
2. HTML 的事实来源是 PSQL 细表，不依赖每日附属大 JSON。
3. HTML 页面承担更高信息密度、更好阅读层级和更清晰次日准备，而不是把 Markdown 原文简单包一层。
4. 页面风格采用 Bear 阅读器式长文体验，使用白、灰、黑作为主体，红色只作为注意力锚点。

## 核心纠偏

本设计不是：

- `Markdown + HTML + 每日完整 JSON` 三件套。
- 为 HTML 额外保存一份完整日报大对象。
- 把现有 Markdown 重新还原成结构化事实。
- 从实时源回补历史 HTML。
- 让漂亮页面掩盖关键事实缺失。

本设计是：

```text
PSQL 细表 -> DailyReportView -> HTML 模板 -> 每日 HTML 阅读产物
```

`DailyReportView` 是运行时阅读视图对象。它可以在生成过程中短暂存在，也可以只记录轻量产物元数据，但不能成为每日完整事实主存。

## 范围

范围内：

- 定义 `DailyReportView` 查询层。
- 定义 HTML 日报的信息架构。
- 定义 PSQL 字段来源、缺失处理、HTML 转义和输出路径。
- 定义后续实现任务分配。
- 保留现有 Markdown 输出。

范围外：

- 不新增每日完整 JSON 文件。
- 不新增每日完整 JSON 表字段。
- 不改写全部日报推理逻辑。
- 不一次性重算所有历史 HTML。
- 不处理独立前端应用、发布站点或分享出口。
- 不把 HTML 当作新的交易判断引擎。

非目标：

- HTML 不负责重新推理。
- HTML 不负责从历史 Markdown 解析事实并回填 PSQL。
- HTML 不用实时数据补历史日期。
- HTML 不输出另一个几百兆级别的附属文件。

## 完成定义

规格完成需要满足：

- 明确 C2 架构：PSQL 细表作为事实来源，Python 查询层组装阅读视图，HTML 模板只负责呈现。
- 明确禁止每日大 JSON 附属产物。
- 明确页面采用 Bear 阅读器风格和网易云红注意力锚点。
- 明确后续实施任务、范围、非目标、验证和限制。
- 后续实现者可以按本规格直接拆计划。

## 现有上下文

当前日报主输出由 `scripts/daily_report_render.py` 组装多个 Markdown 变体并落盘。

仓库已有独立 HTML 先例：`scripts/export/sh_index_chanlun_html.py`。这个先例提供了几条可继承规则：

- HTML 独立落盘。
- 模板渲染和数据分析分离。
- 用户可见文本必须 HTML escape。
- 缺关键数据时停止生成对应 HTML。

仓库已有 PSQL 事实层：`scripts/storage/postgres_daily_fact_db.py` 和 `scripts/storage/database_service.py`。测试中已经要求 PSQL schema 不以 `payload_json` 作为主存，说明当前方向应继续使用细表而不是每日完整大对象。

## 设计原则

1. PSQL 是事实来源。
2. HTML 是阅读产物，不是事实主存。
3. 每日 HTML 可以生成，不能附属一个每日完整 JSON。
4. Markdown 继续保留，不因 HTML 设计而被迫迁移。
5. replay 日期只能使用目标日期已有事实，不从当前实时数据补历史。
6. 页面先服务次日准备，再服务推导审计。
7. 用户可见文字继承本仓库日报术语契约。
8. 缺关键事实时宁可停止生成 HTML，也不输出看似完整但事实不足的页面。

## 总体架构

建议新增三个小模块：

```text
scripts/report/html_report_view.py
scripts/report/html_report_renderer.py
scripts/templates/daily_report_reader.html
```

### `html_report_view.py`

职责：

- 从 `DatabaseService` 查询 PSQL 事实。
- 按交易日组装 `DailyReportView`。
- 标记关键事实是否完整。
- 返回页面需要的小结构，不保存完整大对象。

不得做：

- 不生成 HTML 字符串。
- 不读实时行情源。
- 不解析完整 Markdown 来推导事实。
- 不写每日 JSON 文件。

### `html_report_renderer.py`

职责：

- 接收 `DailyReportView`。
- 使用模板渲染 HTML。
- 对所有文本做 HTML escape。
- 保存 HTML 文件。
- 返回保存路径和轻量元数据。

不得做：

- 不直接查 PSQL。
- 不重新判断交易结论。
- 不把 Markdown 原文作为 raw HTML 注入页面。

### `daily_report_reader.html`

职责：

- 定义 Bear 阅读器式页面结构。
- 定义白、灰、黑、红设计 token。
- 支持桌面和移动阅读。
- 支持长表折叠和章节锚点。

不得做：

- 不引用外部 CDN 作为核心渲染依赖。
- 不引入营销页式装饰。
- 不使用大面积红色背景。

## `DailyReportView` 结构

第一版建议使用 Python dataclass 或普通 dict，但字段名必须稳定。

```text
DailyReportView
- meta
- tomorrow_action
- market_spine
- mainline_evidence
- candidate_actions
- participation_reviews
- data_sources
- diagnostics
```

### `meta`

字段：

- `trade_date`
- `report_title`
- `generated_at`
- `run_mode`
- `data_source_summary`

### `tomorrow_action`

第一屏最重要。字段：

- `position_state`
- `can_participate`
- `primary_target`
- `participation_window`
- `action_summary`
- `cancel_conditions`
- `risk_boundary`

关键规则：

- 如果没有明确参与资格，必须显示不参与。
- 如果条件不完整，必须显示停止生成原因，而不是输出空白动作。
- 红色只用于当前动作、取消条件、风险边界。

### `market_spine`

字段：

- `market_fit`
- `turnover_summary`
- `breadth_summary`
- `market_phase`
- `index_structure`
- `why_it_matters`

### `mainline_evidence`

字段：

- `confirmed_line`
- `supporting_lines`
- `attack_evidence`
- `turnover_share`
- `fund_flow`
- `sector_breadth`
- `continuation_conditions`
- `failure_conditions`

### `candidate_actions`

字段：

- `stock_code`
- `stock_name`
- `role`
- `source_reason`
- `participation_script`
- `entry_timing`
- `buy_window`
- `risk_reward`
- `invalidation`
- `missed_action`

### `participation_reviews`

字段：

- `stock_code`
- `stock_name`
- `review_status`
- `facts`
- `review_summary`
- `next_tracking_action`

### `data_sources`

字段：

- `source_label`
- `source_policy`
- `source_date`
- `query_date`
- `trade_date`
- `status`
- `warning`

关键规则：

- 会随日期变化的数据必须保留日期字段。
- 无法证明属于目标日期的数据不能进入历史 HTML。

### `diagnostics`

字段：

- `missing_required_facts`
- `degraded_facts`
- `render_warnings`
- `html_artifact_path`

## PSQL 来源建议

第一版优先使用已有细表和查询方法，避免新增大而全的表。

候选来源：

- `daily_report_fact_fields`：日报事实字段。
- `market_cycle_days` / `market_cycle_periods`：市场周期事实。
- `sector_attack_evidence_daily`：主线攻击证据。
- `sector_diffusion_score_daily`：板块扩散证据。
- `extreme_conviction_cases`：高确信样本。
- `extreme_conviction_mentions`：日报提及记录。
- `planned_participation_steps`：参与脚本拆解。
- `participation_reviews`：参与预演复盘。
- `report_artifacts`：轻量产物记录。

如现有表不能覆盖某个展示字段，第一版应优先让该字段缺失并报告原因，不为了页面完整新增每日完整 JSON。

## 输出路径

正式输出：

```text
reports/<date>_A股日报_完整版.html
```

replay 输出：

```text
reports/replay/<date>_A股日报_完整版_replay.html
```

如果正式 Markdown 已冻结且本次属于实验生成，HTML 应和现有规则保持一致，优先写入 replay 目录，不覆盖历史正式产物。

## 生成时机

第一版建议在 Markdown 产物保存之后尝试生成 HTML。

规则：

- PSQL 事实完整时生成 HTML。
- PSQL 不可用时不生成 HTML，并记录原因。
- HTML 生成失败不应删除已保存 Markdown。
- 如果 HTML 缺关键事实，停止 HTML 生成，不输出半成品。

后续如果日报主链路迁移到 PSQL 事实层更完整，可以把 HTML 生成提前到更稳定的位置。

## 页面视觉

设计读法：

```text
Bear 阅读器式长文阅读 + 网易云红注意力锚点
```

### 色彩

主体：

- 背景：白色。
- 分区：浅灰。
- 正文：黑色或接近黑色。
- 次级文字：中性灰。
- 分隔线：浅灰。
- 重点色：红色。

建议 token：

```css
--reader-bg: #ffffff;
--reader-surface: #f7f7f8;
--reader-surface-strong: #efeff1;
--reader-text: #111111;
--reader-muted: #6b6b70;
--reader-line: #e5e5e7;
--accent-red: #d33a31;
```

`--accent-red` 允许实现阶段在 `#c20c0c`、`#d33a31`、`#ec4141` 之间截图校准。默认不能用紫色、蓝紫渐变或金融大屏黑底替代。

### 字体与排版

- 正文颜色必须接近黑色。
- 正文宽度受控，优先服务连续阅读。
- 段落、表格、列表之间用留白和浅灰线区分。
- 标题不使用夸张营销页字号。
- 长表默认折叠，关键行展开显示。
- 红色只用于真正需要注意的位置。

### 布局

桌面：

- 左侧章节目录。
- 中间主阅读区。
- 顶部或右侧显示明日动作摘要。

移动：

- 目录收起为顶部章节切换。
- 明日动作摘要优先显示。
- 表格可横向滚动或折叠为字段组。

### 页面章节

建议顺序：

1. `明日动作`
2. `市场结构`
3. `主线证据`
4. `参与对象`
5. `参与预演复盘`
6. `数据来源`
7. `运行诊断`

第一屏必须回答：

- 明天是否参与。
- 最大仓位是什么。
- 参与对象是谁。
- 什么条件出现才可做。
- 什么条件出现就不做。

## HTML 安全与文本规则

- 所有来自日报、PSQL 或用户输入的文本必须 HTML escape。
- 不允许 raw HTML 注入。
- 不允许把完整 Markdown 转成 HTML 作为第一版主路径。
- 表格单元格内容也必须 escape。
- URL 如果展示为链接，必须校验协议，只允许 `http`、`https` 或本地相对路径。
- 用户可见文字必须遵守日报术语契约。

## 缺失处理

HTML 生成需要最少事实条件：

- 目标交易日存在。
- PSQL 可连接。
- `tomorrow_action` 至少能判断参与或不参与。
- `market_spine` 至少能解释市场底色。
- 数据来源能说明关键事实来自哪里。

不满足时：

- 不写 HTML 文件。
- 返回缺失字段列表。
- 在运行日志中记录原因。
- 不从实时源补历史 replay。

可降级字段：

- 历史复盘表。
- 非核心候选列表。
- 长周期统计。
- 运行耗时附录。

可降级字段缺失时，页面可以生成，但必须在 `数据来源` 或 `运行诊断` 中说明。

## 验证设计

后续实现应新增或更新测试：

```text
tests/test_daily_report_html_view.py
tests/test_daily_report_html_renderer.py
tests/test_daily_report_entry_html_output.py
```

验证命令必须使用 Python 3.14：

```bash
.generated/venv-py314/bin/python3.14 -m unittest tests/test_daily_report_html_view.py tests/test_daily_report_html_renderer.py tests/test_daily_report_entry_html_output.py
```

实现完成后还需要至少运行一个 replay：

```bash
.generated/venv-py314/bin/python3.14 scripts/daily_report_entry_demo.py <date> --replay
```

HTML 基础检查：

- 文件存在。
- 标题包含日期。
- 第一屏包含明日动作。
- 正文文本已 escape。
- 不存在未转义脚本标签。
- 没有生成每日完整 JSON 附属文件。

视觉检查：

- 桌面视口正文可读。
- 移动视口第一屏先显示明日动作。
- 红色只用于注意力锚点。
- 正文字体颜色接近黑色。
- 长表不会挤压正文阅读。

## 后续任务分配

### 子任务 1：PSQL 阅读视图契约

模式：Pro

执行者：本地直接做；如果后续明确启用 subagent，使用 gpt-5.5 和 xhigh。

目标：

- 建立 `DailyReportView` 的字段契约和查询入口。

范围：

- 新增 `scripts/report/html_report_view.py`。
- 新增 `tests/test_daily_report_html_view.py`。
- 只读取 PSQL 细表或 `DatabaseService` 已有方法。

非目标：

- 不写 HTML 模板。
- 不接入日报入口。
- 不新增每日完整 JSON。

验证：

- 构造 fake database service，验证交易日、明日动作、主线证据、数据来源可以组装。
- 验证缺关键事实时返回缺失列表。

限制：

- 中文用户可见文字。
- 不覆盖既有未提交改动。
- 不扩大到无关 PSQL 表重构。

输出：

- 变更文件路径。
- 新增 view 字段清单。
- 缺失事实行为说明。

### 子任务 2：HTML 渲染器与模板

模式：Pro

执行者：本地直接做；如果后续明确启用 subagent，使用 gpt-5.5 和 xhigh。

目标：

- 用 Bear 阅读器风格渲染 `DailyReportView`。

范围：

- 新增 `scripts/report/html_report_renderer.py`。
- 新增 `scripts/templates/daily_report_reader.html`。
- 新增 `tests/test_daily_report_html_renderer.py`。

非目标：

- 不查询 PSQL。
- 不解析完整 Markdown。
- 不引用外部 CDN 作为核心依赖。
- 不生成每日完整 JSON。

验证：

- 文本 escape。
- 输出路径正确。
- replay 后缀正确。
- 红白灰黑基础 token 存在。
- 未转义脚本不会进入 HTML。

限制：

- 页面必须是阅读器，不是营销页。
- 红色只用于注意力锚点。
- 正文颜色必须接近黑色。

输出：

- HTML 模板路径。
- 渲染器函数签名。
- 视觉 token 清单。

### 子任务 3：日报入口接入

模式：Pro

执行者：本地直接做；如果后续明确启用 subagent，使用 gpt-5.5 和 xhigh。

目标：

- 在日报生成完成后尝试生成 HTML。

范围：

- 最小修改 `scripts/daily_report_entry_demo.py` 或现有输出保存层。
- 新增 `tests/test_daily_report_entry_html_output.py`。

非目标：

- 不改变 Markdown 保存规则。
- 不改变报告推理逻辑。
- 不新增大型附属文件。

验证：

- PSQL 可用且事实完整时保存 HTML。
- PSQL 不可用或关键事实缺失时不保存 HTML，并记录原因。
- Markdown 保存不受 HTML 失败影响。

限制：

- 只接入最小闭环。
- 不重构日报入口大文件。

输出：

- 接入点说明。
- 失败时运行日志文案。
- 保存路径示例。

### 子任务 4：replay 验证与视觉检查

模式：Pro

执行者：本地直接做；如果后续明确启用 subagent，使用 gpt-5.5 和 xhigh。

目标：

- 用历史日期验证 HTML replay 产物。

范围：

- 跑相关 unittest。
- 跑一个 `<date> --replay`。
- 检查 HTML 基础结构和视觉关键点。

非目标：

- 不做大范围历史回放。
- 不修无关日报内容问题。
- 不补当前实时数据到历史日期。

验证：

- Python 3.14 unittest 通过。
- replay HTML 文件存在。
- 没有每日完整 JSON 附属文件。
- 页面第一屏能看到明日动作。

限制：

- 如 PSQL 历史事实缺失，报告缺失原因，不临时改走实时数据。

输出：

- 命令结果。
- HTML 文件路径。
- 剩余风险。

## 实施顺序

1. 先实现 PSQL 阅读视图契约。
2. 再实现 HTML 渲染器与模板。
3. 再接入日报入口。
4. 最后做 replay 和视觉检查。

每一步都必须能单独验证。任何一步发现需要恢复每日大 JSON，都应停止并回到本规格重新讨论。

## 风险

- PSQL 细表可能暂时缺少页面需要的部分字段。
- 当前日报入口文件较大，接入点要克制。
- HTML 页面如果过度设计，会偏离阅读器目标。
- 如果把 Markdown 原文当成主输入，容易回到不可审计的文本转换路径。

对应处理：

- 字段缺失先报告，不新增大对象兜底。
- 接入只做最小保存调用。
- 视觉以阅读为先，红色只做重点。
- HTML 从 `DailyReportView` 渲染，不从完整 Markdown 反推。

## 规格自检清单

- 没有把每日完整 JSON 作为事实主存。
- 没有设计独立前端发布出口。
- 没有要求一次性迁移 Markdown。
- 没有用 HTML 重新推理交易结论。
- 缺历史事实时不从实时源补 replay。
- 页面风格是 Bear 阅读器式长文阅读。
- 红色只用于需要注意的位置。
