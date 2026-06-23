# Implementation: 日报HTML盘面反馈复盘模块

## Prerequisites

- 使用 Python 3.14：`.generated/venv-py314/bin/python3.14`
- 不使用 subagent，主会话直接实现和检查。

## Ordered Checklist

- [x] I1: 在 `tests/test_daily_report_markdown_html.py` 增加盘面反馈图卡测试。
- [x] I2: 在 `scripts/report/markdown_report_html.py` 增加盘面反馈表解析、payload 写入和图卡插入。
- [x] I3: 在 `scripts/templates/daily_report_markdown_reader.html` 增加 `renderIntradayFeedbackReviewChart`。
- [x] I4: 运行目标测试和格式检查。
- [x] I5: 根据测试结果补小修。

## Validation Commands

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html`
- `git diff --check -- scripts/report/markdown_report_html.py scripts/templates/daily_report_markdown_reader.html tests/test_daily_report_markdown_html.py`
- 对改动文件和任务文档运行用户可见术语检查，确认没有旧工程口径。

## Validation Results

- `.generated/venv-py314/bin/python3.14 -m unittest tests.test_daily_report_markdown_html`：21 tests OK。
- `git diff --check -- scripts/report/markdown_report_html.py scripts/templates/daily_report_markdown_reader.html tests/test_daily_report_markdown_html.py .trellis/tasks/06-23-daily-html-intraday-feedback-review/prd.md .trellis/tasks/06-23-daily-html-intraday-feedback-review/implement.md`：通过。
- 用户可见术语检查：无命中。
- 浏览器预览：本地 HTTP 打开 `.generated/preview/intraday_feedback_review_preview.html`，控制台 0 error / 0 warning，图卡生成 canvas，脚注保留 `1x满仓二选一` 原文。

## Risk And Rollback Points

- 风险文件：`scripts/templates/daily_report_markdown_reader.html` 脚本较长，插入位置要靠近现有 Bear 图表渲染函数。
- 回滚点：新增函数彼此独立，删除 `intraday_feedback_review` 相关代码即可回退。

## Review Checkpoints

- 测试中必须断言 `1x/2x` 账户结论不被改写成 50%。
- 测试中必须断言无有效表格时不出现空白图卡。
