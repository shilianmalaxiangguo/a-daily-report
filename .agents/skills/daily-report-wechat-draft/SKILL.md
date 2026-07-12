---
name: daily-report-wechat-draft
description: "日报生成后，把 HTML 里的《账户日序表》和《板块资金扩散淘汰赛》截图成 PNG，并写入微信公众号草稿。"
---

# Daily Report WeChat Draft

Use this skill when the user asks to put a generated daily report into a WeChat Official Account draft, especially when the request mentions:

- `公众号草稿`
- `生成日报后发公众号`
- `账户日序表截图`
- `板块资金扩散淘汰赛截图`
- `日报自动入草稿`

## Scope

This skill only handles the post-report WeChat draft step:

- read an existing daily report Markdown or HTML file,
- find the matching daily report HTML file,
- screenshot the rendered `账户日序表` and `板块资金扩散淘汰赛` HTML blocks as PNG files,
- build a minimal article body around the screenshots,
- optionally upload the image and create a WeChat draft through the official API.

Do not change daily report generation, candidate selection, final action logic, replay facts, or official historical reports while using this skill.
The skill only creates drafts. The user reviews the draft and schedules or sends it manually in the WeChat UI.

## Background

SkillsMP has broader WeChat skills such as `md2wechat`, `aws-wechat-article-publish`, and `wechat-publisher`. This project skill is narrower on purpose: the daily report already exists, and the repeated work is only to turn fixed Bear HTML sections into a WeChat draft.

## Requirements

Run all project Python commands with:

```bash
.generated/venv-py314/bin/python3.14
```

The helper script uses `Pillow`, `BeautifulSoup`, `requests`, and local Chromium/Chrome. The screenshot source is always the rendered Bear HTML. Markdown is only used to identify the report date, locate the matching HTML, and read the final target.

When creating the remote draft, the script must send the article JSON as UTF-8 bytes with `ensure_ascii=False`. Do not use a request path that turns Chinese text into literal `\u4eca...` sequences in the WeChat draft editor.

If Chromium is not on `PATH`, set:

```bash
CHROMIUM_BIN=/absolute/path/to/chromium
```

For real WeChat draft creation, credentials must be available in environment variables or `.env`:

```bash
WECHAT_APP_ID=...
WECHAT_APP_SECRET=...
```

Multi-account names are also supported:

```bash
WECHAT_1_APPID=...
WECHAT_1_APPSECRET=...
```

## Workflow

1. Confirm the report exists. If the user did not provide a path, use the newest `reports/*_A股日报_完整版.md`.
2. Build local artifacts first:

   ```bash
   .generated/venv-py314/bin/python3.14 .agents/skills/daily-report-wechat-draft/scripts/daily_report_wechat_draft.py --latest
   ```

   To force a specific HTML source:

   ```bash
   .generated/venv-py314/bin/python3.14 .agents/skills/daily-report-wechat-draft/scripts/daily_report_wechat_draft.py reports/2026-07-08_A股日报_完整版.md --html-report reports/2026-07-08_A股日报_完整版.html
   ```

3. If the user wants the draft created and credentials are configured, create the WeChat draft:

   ```bash
   .generated/venv-py314/bin/python3.14 .agents/skills/daily-report-wechat-draft/scripts/daily_report_wechat_draft.py --latest --create-draft
   ```

4. Report the generated PNG paths, local preview path, and WeChat draft `media_id` when available.

## Draft Content Contract

The draft article must use this exact shape:

1. `账户日序表` image from Bear HTML.
2. `板块资金扩散淘汰赛` image from Bear HTML.
3. `今日标的：<target>` where empty target displays as `空仓`.
4. `模拟持仓，不作为投资买卖依据`.

Default title:

- no 明日执行对象: `今日空仓`
- has 明日执行对象: `今日策略`

Do not add explanatory paragraphs, keyboard shortcuts, scheduling instructions, or extra report text to the article body.

## Safety Rules

- This skill creates a draft only. It must not call WeChat publish or mass-send APIs.
- Do not print `APPID`, `APPSECRET`, `access_token`, or full request payloads that may contain credentials.
- Use only the official `https://api.weixin.qq.com` base URL for real draft creation.
- If credentials are missing, stop after local artifact generation and tell the user which environment variable names are expected.
- If the HTML file, target section, or target table block is missing, stop and report the path that failed.
- Store generated local artifacts under `output/wechat-drafts/<date>/` unless the user provides `--out-dir`.
- Default title is `今日空仓` when the report has no 明日执行对象, otherwise `今日策略`.
- The article body is the screenshots, then `今日标的：...`, then `模拟持仓，不作为投资买卖依据`.
- If a created draft shows literal Unicode escape text such as `\u4eca`, treat it as a bug in request encoding and create a corrected draft after fixing the UTF-8 request body.

## Outputs

For a report dated `YYYY-MM-DD`, the script writes:

- `output/wechat-drafts/YYYY-MM-DD/account-day-order.png`
- `output/wechat-drafts/YYYY-MM-DD/account-day-order.capture.html`
- `output/wechat-drafts/YYYY-MM-DD/sector-fund-spread-tournament.png`
- `output/wechat-drafts/YYYY-MM-DD/sector-fund-spread-tournament.capture.html`
- `output/wechat-drafts/YYYY-MM-DD/cover.jpg`
- `output/wechat-drafts/YYYY-MM-DD/article_preview.html`
- `output/wechat-drafts/YYYY-MM-DD/draft_payload.json`
- `output/wechat-drafts/YYYY-MM-DD/result.json`
