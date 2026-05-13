# snap-ui 发布契约

## 核心规则

snap-ui 线上发布必须先完成本地数据与构建资产验收。Cloudflare Pages 的构建分支是 `develop`；不要在没有定位坏资源 URL 前手动反复 redeploy。

## 数据验收

- 每次 fresh daily generation 后，先运行 snap-ui public data 生成节点。
- Tushare 是 public data 的结构化首选来源，生成产物必须通过本地 contract check。
- 最小验收包含 `tests/unit/publicStaticDataContract.test.ts`，确认 latest date、日报索引、stock 3D、市场光照、成交额结构等 public JSON 足够前端消费。
- 对同一天的 report ref，必须同时检查页面实际消费的视觉 ref。`work-page` 的 `上证指数 · 新缠论日线中枢` 需要 `/data/snap-ui/zhongshu-structure/<date>-sh000001.json`；只有 mainline-series ref 不算完整。
- runtime API 返回 200 但 `rows: []` 时不能阻断静态 JSON fallback。空成功是不可用数据，必须继续读取 `/data/snap-ui/.../<date>-<mode>.json`。
- 成交额图只有一个交易日点时，ECharts 仍必须有可见点或可见图形，不能把 symbol、lineStyle 全部隐藏后让图像看起来空白。

## 构建验收

- build 前 clean .output and dist。
- build 后执行 `verify-pages-module-assets`，确保 HTML 引用的 `_nuxt/*.js` 都真实存在。
- 线上抽检 module URL 的 Content-Type 必须是 `application/javascript`，不能是 `text/html`。

## Cloudflare Pages module MIME 事故处理

出现 module MIME 报错时，先抓生产 HTML，提取所有 `_nuxt/*.js` module/modulepreload 引用，再逐个检查 HTTP status 与 Content-Type。若某个 JS 返回 `text/html`，说明 HTML 与 `_nuxt` hashed asset 发生错配；先修构建产物和分支，再考虑重新发布。

## 验收标准

- snap-ui public data contract check 通过。
- `verify-pages-module-assets` 通过。
- `develop` 分支包含已验证提交。
- 至少一个线上 `_nuxt/*.js` 响应头为 `application/javascript`。
- 最新 report date 的中枢视觉、stock 3D、市场光照、Top50 成交额、主线成交额静态 JSON 都能本地读取，且日期等于 latest date。
