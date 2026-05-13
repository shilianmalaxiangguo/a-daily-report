# 2026-05-13 Cloudflare Pages module MIME 反思

## 事故

Cloudflare Pages 线上页面加载 `_nuxt/*.js` 时返回 `text/html`，浏览器报 module MIME 错误：期望 JavaScript-or-Wasm module script，但服务端返回 HTML。实际坏 URL 是 HTML 里引用的入口 JS；该 JS 路径被 SPA fallback 命中，返回了 HTML。

## 根因

发布目录出现 HTML 与 `_nuxt` 资产错配。首页 HTML 引用了某个 hashed module 文件，但 `dist/_nuxt` 内没有对应文件，Cloudflare 对该路径返回了 HTML。

## 固化动作

- build 前 clean .output and dist，避免新旧构建产物混在一起。
- build 后执行 `verify-pages-module-assets`，逐个检查 HTML 引用的 `_nuxt/*.js` 是否存在。
- 线上报错时，do not manually redeploy before identifying the bad asset URL。先解析生产 HTML，找到具体 module URL，再查 HTTP status 和 Content-Type。
- 验收必须包含线上 JS 响应头：`application/javascript`。

## 下次处理顺序

1. 抓取生产 HTML。
2. 提取所有 `_nuxt/*.js` module/modulepreload 引用。
3. 对每个引用查响应头。
4. 如果返回 `text/html`，先比对当前构建产物是否含该文件。
5. 本地 `npm run build` 必须通过 `verify-pages-module-assets` 后再推送。

## 同日补充：静态数据完整性

同一天的日报索引更新不等于 snap-ui 视觉数据完整。2026-05-13 曾出现 report ref 已经到 5/13，但 `zhongshu-structure` 缺少 5/13 的 sh000001 视觉文件，导致工作台仍显示 5/12 中枢；同时 runtime API 返回 200 空数组会让主线图跳过静态 fallback。

后续发布前必须额外确认：

1. `/data/snap-ui/zhongshu-structure/index.json` 的 latest date 同时包含 report ref 和 sh000001 visual ref。
2. `/data/snap-ui/structure-lab/<latest>-frozen.json` 的 `meta.date`、个股 3D 最新 K 线、市场光照最新 context 都等于 latest date。
3. `/data/snap-ui/turnover/top50-share/latest.json` 有 latest row、latest sector breakdown、sector breakdown series，并且单点图也可见。
4. 主线成交额组件把 200 空数组当作不可用数据，继续读取 public JSON fallback。
