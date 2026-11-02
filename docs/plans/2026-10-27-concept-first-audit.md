# 概念优先日报：实施与核验记录

> 历史实施记录，已冻结；不属于当前小盘日报入口或桌面验收清单。

日期：2026-10-27。目标事实日：2026-10-26。边界与逐项待办见[本轮 TODO](2026-10-27-concept-first-daily-todo.md)。本文件不授权提交、发布或覆盖正式历史。

## 1. 结果与事实边界

- 当前采集显式请求同花顺A股概念目录 `type=N`，目标日榜单、历史价格和冷暖共用代码身份；行业 `type=I` 分开保存，不回退改名为概念。
- 本次原目录395个；按目录原名排除5个样本股/成份股篮子，主题目录390个。390个有部分历史路径，目标日389个有有效价格；这不是目标日390个全部齐备。
- 逐日净额窗口为10月16、19、20、21、22、23、26日。前6日各匹配386个概念，26日匹配385个；缺失不补零。来源定义为 `moneyflow_cnt_ths.net_amount`，单位亿元，不用已取整买卖分项替换。
- 原接力不再显示在当前概念页；原始记录仍在修订快照中，正式历史原件和旧行业历史页不删除。价格比较、冷暖、日期选择和市场图表保留。
- 同名图例以代码区分；同窗路径与本次成分重复只作提示，不合并代码。Top50原数值保留：19、20日复算匹配含北交所范围；22、23、26日匹配沪深范围；另外20个历史点范围未核实，显示独立点。
- 现有成分详情补同五个交易日日收益复利比较，不增加选股器、综合买入分数或交易指令。个股和指数价格口径的限制、最新成分的查询日分别披露；并非可成交净收益或已识别alpha。

## 2. 变更集只读分类

实施前工作区已存在1018条状态记录，并非本轮从干净提交开始。原始状态与941个正式文件指纹保存在 `.generated/concept-first-20261027/baseline.json`。

逐文件分类见 `.generated/concept-first-20261027/change-scope.tsv` 和对应 JSON。它们分别记录状态、实施前是否已有、本轮责任、可并存分类及理由，不用整个Git差异冒充本轮改动。

- `.trellis/` 500项删除、`.claude/` 44项删除、`.codex/agents/trellis-*` 3项删除：既有工具流程变动，与本轮概念阅读无关，应拆出。本轮不删除、不恢复。
- 旧Wiki删除属于先前知识重建；本轮仅更新4份现行入口/方法说明，不接管旧文件删除。
- 根目录PNG/TXT和 `wiki.zip`：单列为生成或散件，不混入代码提交。压缩包未展开审查，标记为可能不应提交；不因文件名判定其中必有凭证。
- 受检变更文本未检出所扫描的实质凭证格式；这是有限格式扫描，不是完整保密保证。私有环境和被忽略目录不因此获得提交许可。对话中出现的密钥不复制进产物，建议轮换。

代码核对使用本轮保存的脏工作区原文作为基线；未清理、暂存或提交先前改动。

## 3. 真实入口与旧逻辑可达性

当前调用关系：

```text
daily_report_entry_demo.main
  -> 解析并拒绝旧账户/单票/正式覆盖参数
  -> full：仅定位已有历史原件并返回；short：停止
  -> load_data_snapshot(显式来源) 或 collect_market_reading_data(显式采集)
  -> build_market_reading_preflight（市场、板块事实）
  -> _save_standalone_sector_reading_page
  -> save_sector_daily / render_sector_daily
  -> 事实图表、概念净额及原数值核对
```

| 核对项 | 文件、符号与关键原文 | 结论 |
| --- | --- | --- |
| 默认输出 | `scripts/daily_report_entry_demo.py:6179` `_resolve_daily_report_output_mode`：`return "sector"` | 没有按账户参数隐式选择旧链。 |
| 旧参数 | `scripts/daily_report_entry_demo.py:6301` `main`：旧参数条件后 `parser.error(...)` | `--position`、`--stock`、`--overwrite-official`均在事实I/O前拒绝；包括与full组合。 |
| full/short | `scripts/daily_report_entry_demo.py:6299`、`scripts/daily_report_entry_demo.py:6321` `main`：short报错；full定位后 `return` | full不是旧生成开关，short不调用旧共识。 |
| replay来源 | `scripts/daily_report_entry_demo.py:6337` `main`：`load_data_snapshot(target_date, mode=snapshot_mode)` | 选定来源缺失停止，不切另一版本。 |
| 唯一采集分支 | `scripts/daily_report_entry_demo.py:6377` `main`：`if selected_data_path == "live"` | replay不会进入采集器。 |
| 当前检查 | `scripts/daily_report_render.py:1483` `build_market_reading_preflight`：`sector_facts(...)`；结尾 `"decision_checks": []` | 不把账户和唯一对象作为当前必需条件。 |
| 页面生成 | `scripts/daily_report_entry_demo.py:6411` `main`：`_save_standalone_sector_reading_page(...)` | 不调用 `build_report_outputs` 或旧完整重算。 |
| 页面同源 | `scripts/daily_report_entry_demo.py:5631` `_save_standalone_sector_reading_page`：`source_mode in (...)`；`scripts/report/sector_reading_history.py:184` `historical_assets`：比较 `snapshot_hash` | 仅选定模式已有页面可作留存来源；页面与快照不同不能混用。 |
| `selection_workflow` | `scripts/daily_report_entry_demo.py:4338` `_restore_postgres_sector_first_runtime_facts`：`report_runtime._build_runtime_selection_workflow(...)` | 旧恢复函数仍存在；当前main不调用，离线跟踪未执行。 |
| `two_layer_decision_payload` | `scripts/daily_report_entry_demo.py:5586` `_sector_capital_source_payloads`：`data.get("two_layer_decision_payload")` | 旧来源汇总仍存在，当前main不进入；当前事实投影不读取该决定。 |
| `execution_chain` | `scripts/daily_report_entry_demo.py:181` 模块导入：`from domains.execution_chain...` | 仍有导入，不能声称代码物理消失；本次运行未执行其中业务函数。 |
| `position_context` | `scripts/daily_report_entry_demo.py:3944` `build_personal_position_context`：`return run_build_personal_position_context(...)` | 旧包装仍在；当前路径和运行跟踪未调用。 |
| `compact_bear_report` | `scripts/report/sector_daily_report.py:17`：`_finite_number, _text`；`:257`：`_seal_section, seal_rows` | **部分可达**：复用事实、封板和HTML助手。不是旧精简报告生成或账户推演；不能笼统宣称整个模块不可达。 |
| `daily_report_consensus` | `scripts/daily_report_entry_demo.py:476` 模块导入；`:6256` `_run_daily_report_consensus_short` 直接抛出停止信息 | 导入会定义类，运行跟踪中的两条类定义不等于共识生成；本次没有执行共识业务函数。 |

完整符号位置及所属函数见 `.generated/concept-first-20261027/entry-symbol-references.json`。动态证据见 `offline-replay-trace.json`；单测 `MarketReadingEntryTest._run` 对旧数据、账户、诊断、重算和数据库写入函数设置禁止调用断言。该证据针对当前入口和所测分支，不是对任意外部脚本调用的全局证明。

## 4. 日期、来源、原始与派生

必要字段分工：事实日/来源日为26日或窗口内明确交易日；实际查询/取得在27日。当前目录和最新成分只证明本次查询身份，不补造当时成员。净额原始页、参数、覆盖、单位、服务主机与派生矩阵分开保存；价格 `price_inputs` 可重建路径、冷暖和累计窗口。

本次实际数据服务为 `x.minitick.top` 的Tushare兼容接口，不冒称直接连接官方Tushare。官方文档只用于核对接口语义和单位；兼容服务数据准确性仍需来源校验。问财三个技能此前已安装，不把三个相同后端的查询当成三个独立来源，也不重复安装或复制凭证。

原始请求清单：`.generated/concept-first-20261027/raw-manifest.json`。日期反例覆盖未来目标日、错来源日、缺取得时间、未来取得时间、查询日矛盾、错请求日期、错单位及同日冲突；冲突倒序仍拒绝。旧冻结事实缺少部分上游凭据时原样披露，不伪造补齐。

数值记录见 `.generated/concept-first-20261027/independent-values.json`；该记录部分使用生产函数生成，本身不算独立计算证据。另以完全不导入日报计算模块的 `raw_independent_check.py`，从72份保存的原始响应逐代码、逐日期核对，使用 Decimal 复算；结果见 `.generated/concept-first-20261027/raw-independent-check.json`：

- 机器人概念 `885517.TI`：23日+238亿元，26日-104亿元；AI应用 `886108.TI`：26日+18亿元。它们是各自来源净额，不是互相转入转出的金额。
- `881277.TI` 与 `884085.TI` 同窗路径及本次26只成分集合相同；保留不同代码，不当作两份独立扩散证据。
- 焦点科技 `002315.SZ` 的20、21、22、23、26日日收益复利约+13.3950%；原行业 `700491.TI` 约+13.8015%；差约-0.4065个百分点。绝对涨幅大不代表相对增强，也不将该行业改名为AI应用。
- 20日原Top50分子约2583.223647亿元，原占比17.55468046%匹配含北交所分母14715.298591亿元；沪深分母14559.988579亿元则得到17.74193457%，不能连作同一种占比。

独立十进制逐股取整与旧浮点逐股取整在受检分母上有约0至0.000004亿元尾差，占比差小于0.00000001个百分点；不据此覆盖原图数值，也不把“精确复现旧浮点尾数”当成独立来源一致。上述核对证明计算与原始响应相符，不证明兼容服务本身无误。

## 5. 验证记录

- 先增加失败反例再修改：初始 `red-tests.log`、中途 `first-green.log`、交互补充 `tooltip-red.log`均保留。首次浏览器发现旧提示读取新列表的问题，见 `browser-failed-1.json`；修复为每次绘图保存自身行集并清除旧提示。
- 初轮Python3.14定向回归239项通过；独立复核补反例后，13个受影响模块242项通过，另11项创新高留存修订兼容通过。最终合并运行14个模块253项，28.966秒通过，见 `final-acceptance-tests.log`，包含只有来源日而无事实日期的拒绝反例。不宣称整个仓库测试通过。旧行业作为概念主榜回退的两项预期按新边界改成行业背景，原价格、样本和日期断言保留。
- 最新实际Chrome/ECharts桌面20项检查通过，见 `browser-results.json` 及 `review-browser.log`：真实概念格子点击、日期双向联动、窗口外清除与返回恢复、反向选择同步、默认多行保留、缺失、来源展开、同名图例鼠标点击及恢复、Top50分段、成分同窗、期货20/60日和16张非空画布。390px不作为本轮固定条件。
- 三份受改JavaScript模板通过 `node --check`；`git diff --check` 无输出且退出0。本轮24份责任文件另作差异空白检查，有实施前原文的按脏基线、其余检查完整文本；结果见 `focused-diff-check.json`，无问题，不把Git只检查已跟踪文件当成全部已查。
- 明确所选来源的最新CLI和禁止联网的运行分别记录在 `review-standard-replay.log`、`offline-replay-2.log`。重复产物一致性见 `replay-consistency.json`；正式文件保护与未改市场事实见 `final-verification.json`。

### 独立复核发现与修正

两位干净上下文子代理分别核对来源/计算和真实页面，各发现2项P2；以下均先补能失败的反例，再由主线程最小修正。`review-red-tests.log` 保存3个新增测试中10个失败分支，`review-green-tests.log` 的73项定向测试及后续242项回归通过。

| 问题与原反例 | 最小修正位置和关键原文 | 新鲜验证 |
| --- | --- | --- |
| 留存页可把机器人26日净额改为999并重算内部指纹，所选快照仍为-104，却可被接受 | `scripts/report/sector_reading_history.py:199`，`historical_assets`：验证快照自身日期/指纹，并以 `if result != native` 拒绝不同事实 | 新增测试分别重算全部页面指纹、破坏原生指纹，均拒绝；正常重复渲染保留 |
| 排名忽略来源日，价格路径忽略来源日/日期矛盾，归一后丢掉反例 | `scripts/report/sector_fact_loader.py:66`，`_row_date` 包含 `trade_date/date/source_date`，并保留至少提供事实日期的要求；`scripts/report/sector_reading_sources.py:13`、`:42`，`build_index_view` 在归一前复用核对 | 概念榜、历史与全A基准的冲突/非法日期拒绝；只有来源日而无事实日期也拒绝；诚实的晚查询日仍可接受 |
| 价格选10月15日，七日净额仍显示26日-104和旧选中格 | `scripts/templates/sector_concept_flow.js:76`，`trend-selection-change`：`selected=null` 并说明所选日不在窗口 | Chrome确认旧金额和选中格清除；返回23日恢复+238 |
| 价格端从机器人换AI应用，详情变AI，但选择器/矩阵仍是机器人 | `scripts/templates/sector_concept_flow.js:74`，同监听器按精确代码同步 `selector.value`；已在默认多行中的对象保持多行 | Chrome确认AI应用23日+135、选择器和唯一矩阵行一致；默认多行保留18行 |

额外一次针对修正的子代理复查未能启动：本地模型转发服务连接被拒绝。没有将这次失败计入审查通过，也不声称修正后又通过了新的独立复查。修正后的证据为主线程的新鲜失败/通过记录、原始行独立算法复算和真实浏览器检查；先前两位独立审查的发现及边界均保留。

产物：`reports/replay/2026-10-26_A股日报_板块日报_replay.html`；独立快照：`snapshots/replay/2026-10-26_replay.json`。只重建必要概念事实，不重新采集或重算原市场、账户与旧完整建议。

## 6. 尚不能证明什么

价格和净额接口并不覆盖每个概念每一天；物理AI/AI漫剧的独立同名价格指数仍未核实。最新成员存在历史归属限制；Top50仍有20个未核实范围的历史点。市场图表原有来源缺口未冒充已修齐。单元测试、重放和漂亮页面都不证明用户采用后更赚钱；阅读是否省时、相对选择是否改善，需要后续真实使用及未参与改规则的样本。

## 7. 再次回答四个专业问题

1. **专业人士会额外做什么**：把“对象和计算没错”“页面帮助判断”“策略带来净收益”分开验收，主动寻找能推翻结论的反例；本轮做到前一项及交互核验，后两项不能顺手宣布成立。
2. **先从什么开始**：带代码、类型、事实日和真实取得时间的原始目录、指数日线、概念净额、成分查询与个股日线、交易日历、请求参数及原始响应指纹；不是旧日报摘要、名称联想、图例或涨幅赢家。
3. **具体方法和工具**：同代码同日核对、分页和覆盖核对、相反顺序冲突测试、同窗日收益复利、原始行Decimal独立复算、正式文件SHA-256保护、Python3.14 unittest、Node/ECharts及真实Chrome交互。没有另建选股、账户或数据平台。
4. **什么能从外部支持正确**：原始响应与派生数值可交叉复算，错误输入得到预定结果，实际点击对象/日期一致，离线重复产物一致且正式历史不变。这些证据支持数据和实现可信；数据源真值仍需真正独立来源，使用价值需实际阅读反馈，盈利有效性需未参与调整的后续样本与可实现成本。

## 8. 下一轮最小提示词

> 不再增加日报栏目、评分、图表或交易规则。基于这轮概念优先修订，在正常生成的日报中积累实际阅读反馈；先区分对象/日期/口径错误，与“看了仍不能作比较”的问题。没有可复现问题就不改代码。
>
> 有问题时，从对应代码与目标日的原始行、请求参数、来源时间和实际页面选择开始，写清输入、实际结果、预期结果以及应保留的正确样本。先补失败反例，再只改最小责任代码；缺数不补零，行业不冒充概念，不用最新成分证明历史归属，不解释为板块间资金转账。
>
> 对“板块已强、个股是否值得承担额外风险”只核对同窗可比事实和实际可成交成本；没有已核实的可交易工具映射就明确未知，不新建选股器，不凭历史涨幅差宣称alpha。若要评价方法效果，预先写清观察样本、比较基准、成本与反证，不拿调整时用过的样本充当后续验证。
>
> 只在有新事实时处理现有缺口：物理AI/AI漫剧精确指数身份、未核实Top50范围、真正独立数据源或历史成分；各自成单独的小任务，不打包扩大本轮。任何历史修正只写所选来源的独立replay，核对正式原件指纹。交付复现、最小修改、测试/真实交互证据和剩余未知；不自动提交或发布。
