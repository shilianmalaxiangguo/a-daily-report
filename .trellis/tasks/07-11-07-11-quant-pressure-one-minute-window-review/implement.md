# Implementation: 一分钟量化压力案例与交易窗口复核

## Prerequisites

- 使用 Python 3.14 固定解释器。
- 先验证三例一分钟主源和交叉源，再写公式结论。
- 不触碰工作区已有的日报主链和无关改动。

## Ordered Checklist

- [x] I1: 抓取并冻结三例通达信一分钟事实，完成时间、OHLC、量额、日聚合、哈希与跨源校验。
- [x] I2: 先补数据契约和公式方向测试，再实现独立一分钟研究计算。
- [x] I3: 计算全日/下降段公式比较、起点敏感性和窗口前缀字段，生成机器可复算结果。
- [x] I4: 对三窗口逐例给出“当时可知 / 后续验收 / 适用角色”，并写清第二窗口的两个子阶段。
- [x] I5: 重写研究 HTML，纳入三例一分钟图、公式族、窗口矩阵和 T+0 → T+1 → T+2 研究协议。
- [x] I6: 运行限定测试、回归、HTML 解析和浏览器桌面/窄屏检查；`file://` 受限时通过本地只读静态服务完成真实 Playwright 复核。
- [x] I7: 启用独立子代理完成数据、数学与提交前审计，修复范围内问题后等待用户确认提交。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest <本任务新增测试模块>`
- `.generated/venv-py314/bin/python3.14 <本任务研究脚本> --fixtures <一分钟fixture目录>`
- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_quant_pressure_replay_runtime`
- `.generated/venv-py314/bin/python3.14 -m html.parser reports/research/quant-pressure-replay-study-20260711.html`
- `git diff --check -- <本任务限定路径>`

## Risk And Rollback Points

- 若 1 分钟源与日线聚合不一致，停止公式计算并保留缺失说明。
- 若模型排名随起点显著改变，报告结论降级为形状竞争，不选唯一公式。
- 若窗口字段引用未来分钟，停止报告生成并修复前缀隔离。
- 若页面修改影响正式日报文件，按越界处理并撤回该部分改动。

## Review Checkpoints

- RC1: 三例、日期、粒度、单位和来源准确。
- RC2: 普通对数与临界对数方向、幂律极限和参数计数准确。
- RC3: 三窗口使用事前数据且角色结论不过度外推。
- RC4: T+1/T+2 未发生事实、资金重叠和 B1/B2 表达准确。
- RC5: 提交前限定 diff、测试与浏览器证据完整。
