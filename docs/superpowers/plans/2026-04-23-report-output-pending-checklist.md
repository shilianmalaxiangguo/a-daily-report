# 2026-04-23 日报输出待完成清单

## 当前已收口

- [x] 正文开头已去掉 `交易理念底线 / 阅读模式 / 实验重放模式 / 真实持仓说明`
- [x] 主报告已移除 `数据获取与执行步骤清单` 附录
- [x] `放量异常 / 龙虎榜 / 共振评分 / AI量化交易信号` 的枚举对象已改成人类可读文本，不再直出 `__enum__`
- [x] `最终结论` 已去掉 `stage_key` 这种内部字段，改成直接面向交易动作的两列表达
- [x] `核心交易哲学：看好A，干A！` 已不再塞进正文尾部
- [x] `2026-04-23 --replay` 已重新生成成功

## 待完成

- [ ] 修复 `放量异常检测` 中部分个股涨跌幅仍显示 `+0.00%`
  - 现象：`昊华能源 / 齐心集团 / 怡达股份 / 通达电气 / 亿道信息` 这类票在正文里仍是 `+0.00%`
  - 已定位：这批异常股不一定落在 `stocks_with_history`，所以仅靠候选历史回填不够
  - 下一步：从 `zt_pool / dt_pool / lianban_data / turnover_rank / stock_full_info` 再补一层真实涨跌幅兜底
  - 验收：上述股票在 [2026-04-23_A股日报_完整版_replay.md](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/reports/replay/2026-04-23_A股日报_完整版_replay.md) 不再出现明显错误的 `+0.00%`

- [ ] 给“异常涨跌幅兜底”补失败测试
  - 目标文件：
    - [test_market_activity_infer.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/tests/test_market_activity_infer.py)
    - [test_market_activity_domain_report_sections.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/tests/test_market_activity_domain_report_sections.py)
  - 验收：补完后跑相关用例全绿，再跑一次真实 replay

- [ ] 继续压缩正文里仍偏“解释型”的段落
  - 当前仍偏啰嗦的位置：
    - `明天仓位怎么放` 章节下的两段 `> 说明`
    - `AI市场洞察总结`
    - 个别 `数据来源 / 说明` 文案
  - 目标：只保留会影响决策的句子，不保留“背景介绍型”句子
  - 验收：正文第一屏直接进入纪律、环境、结论，不需要先读说明

- [ ] 评估是否把 `AI市场洞察总结` 下沉到附录或独立分析版
  - 原因：用户明确要“直接、直观、有目标目的”，这段更像复盘摘要，不一定要留在正式执行版正文
  - 备选方案：
    - 保留在全量版、移出执行摘要
    - 挪到独立附录报告
    - 完全去掉，仅保留日志

- [ ] 如果还需要附录信息，改成单独文件落盘
  - 当前状态：主报告正文已去掉附录，但还没有单独输出 `appendix.md`
  - 建议输出：
    - `reports/replay/2026-04-23_A股日报_附录_replay.md`
    - 或仅保留在运行日志里
  - 验收：正文无附录，附录信息仍可追溯

## 本轮关键文件

- [daily_report_render.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/daily_report_render.py)
- [trading_philosophy.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/knowledge/trading_philosophy.py)
- [use_report_tail_summary.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/hooks/report/use_report_tail_summary.py)
- [final_conclusion_renderer.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/report/final_conclusion_renderer.py)
- [runtime.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/report/runtime.py)
- [report_sections.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/domains/market_activity/report_sections.py)
- [infer.py](/Users/chaixixi/.hermes/hermes-skills/personal/a-daily-report/scripts/domains/market_activity/infer.py)

## 建议执行顺序

1. 先补“异常涨跌幅兜底”失败测试
2. 再补原始行情池涨跌幅回填
3. 跑相关 `unittest`
4. 重新跑 `python3 scripts/daily_report_entry_demo.py 2026-04-23 --replay`
5. 最后再决定是否继续裁掉 `AI市场洞察总结 / 说明型文案`
