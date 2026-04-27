# Snapshot Visual Analysis UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent local Nuxt dashboard in `snap-ui/` for visual daily snapshot analysis, with a mainline funding smooth-line chart and observation-pool K-line/volume charts.

**Architecture:** `snap-ui/` is an ignored child project with its own git repository. Nuxt server routes read JSON snapshots from the parent `a-daily-report` checkout, normalize them into typed JSON contracts, and Vue components render the dashboard using Nuxt UI and ECharts.

**Tech Stack:** Nuxt 4, Vue 3, Nuxt UI, Tailwind CSS v4 theme tokens, ECharts, vue-echarts, TypeScript, Vitest, Happy DOM, Playwright.

---

## File Structure

Parent repository files:

- `docs/superpowers/plans/2026-04-27-snapshot-visual-analysis-ui-implementation-plan.md`: this implementation plan.
- `docs/superpowers/specs/2026-04-27-snapshot-visual-analysis-ui-design.md`: approved product and UI spec.
- `.gitignore`: already ignores `snap-ui/`.

Independent UI project files under `snap-ui/`:

- `nuxt.config.ts`: Nuxt UI, app metadata, server route configuration.
- `app.config.ts`: Nuxt UI semantic color aliases and icons.
- `app/assets/css/main.css`: Tailwind v4 CSS-first tokens for the white / grey / WeChat-green theme.
- `app/app.vue`: wraps the app in `<UApp>`.
- `app/pages/index.vue`: dashboard page.
- `app/types/snapshot.ts`: shared API response types for snapshot refs, mainline rows, pool rows, and K-line rows.
- `app/composables/useSnapshotDashboard.ts`: client-side state orchestration for date, mode, range, pool filter, selected stock, and API fetches.
- `app/utils/charts/mainlineOptions.ts`: pure ECharts option builder for the smooth-line chart.
- `app/utils/charts/klineOptions.ts`: pure ECharts option builder for candlestick + volume chart.
- `app/components/SnapshotToolbar.vue`: date/mode/range/filter controls.
- `app/components/MainlineFundingPanel.vue`: headline metrics and mainline line chart.
- `app/components/MainlineStateStrip.vue`: compact current mainline state.
- `app/components/ObservationPoolWorkspace.vue`: pool list plus selected-stock chart.
- `app/components/PoolGroupList.vue`: grouped observation-pool list.
- `app/components/StockKlineVolumeChart.vue`: selected-stock candlestick + volume chart.
- `app/components/DataStatusBadge.vue`: consistent missing/degraded/success source state.
- `server/utils/sourcePath.ts`: resolves and validates the parent `a-daily-report` data root.
- `server/utils/snapshot/scanner.ts`: lists frozen/replay snapshot refs.
- `server/utils/snapshot/mainlineAdapter.ts`: extracts normalized mainline rows and overview.
- `server/utils/snapshot/observationPoolAdapter.ts`: extracts, groups, and dedupes observation-pool rows.
- `server/utils/snapshot/klineAdapter.ts`: extracts K-line rows from available snapshot data.
- `server/api/snapshots/index.get.ts`: lists available dates/modes.
- `server/api/snapshots/[date]/overview.get.ts`: returns overview for one date.
- `server/api/mainline-series.get.ts`: returns normalized multi-day mainline series.
- `server/api/observation-pool.get.ts`: returns grouped pool rows for one date.
- `server/api/observation-pool/[code]/kline.get.ts`: returns K-line rows for selected stock.
- `tests/unit/*.test.ts`: unit tests for scanner, adapters, chart option builders.
- `tests/e2e/dashboard.spec.ts`: Playwright smoke/visual check.

## Task 1: Scaffold Independent Nuxt Project

**Files:**
- Create: `snap-ui/`
- Create: `snap-ui/package.json`
- Create: `snap-ui/nuxt.config.ts`
- Create: `snap-ui/app/app.vue`
- Create: `snap-ui/app/pages/index.vue`
- Create: `snap-ui/.git/`
- Verify: parent `.gitignore`

- [ ] **Step 1: Verify parent ignores `snap-ui/`**

Run from the parent repository:

```bash
git check-ignore -v snap-ui/package.json snap-ui/app.vue snap-ui/.git/config
```

Expected output includes:

```text
.gitignore:14:/snap-ui/	snap-ui/package.json
.gitignore:14:/snap-ui/	snap-ui/app.vue
.gitignore:14:/snap-ui/	snap-ui/.git/config
```

- [ ] **Step 2: Create the Nuxt app**

Run from the parent repository:

```bash
npm create nuxt@latest snap-ui -- --packageManager npm --gitInit --no-install
```

Expected:

```text
Successfully created project snap-ui
```

- [ ] **Step 3: Install UI, chart, validation, and test dependencies**

Run:

```bash
cd snap-ui
npm install
npm install @nuxt/ui echarts vue-echarts zod
npm install -D vitest happy-dom @vue/test-utils @types/node @playwright/test
```

Expected:

```text
added
```

- [ ] **Step 4: Add stable npm scripts**

Modify `snap-ui/package.json` so the scripts block contains:

```json
{
  "scripts": {
    "build": "nuxt build",
    "dev": "nuxt dev --host 127.0.0.1 --port 3040",
    "generate": "nuxt generate",
    "preview": "nuxt preview --host 127.0.0.1 --port 3040",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  }
}
```

- [ ] **Step 5: Verify the independent repository boundary**

Run:

```bash
git status --short
git -C snap-ui status --short
```

Expected:

```text
# parent output does not include snap-ui files
# snap-ui output shows scaffolded files inside the independent repo
```

- [ ] **Step 6: Commit the scaffold inside `snap-ui`**

Run:

```bash
git -C snap-ui add .
git -C snap-ui commit -m "chore: scaffold Nuxt snapshot UI"
```

Expected:

```text
[main ...] chore: scaffold Nuxt snapshot UI
```

## Task 2: Configure Nuxt UI Theme And App Shell

**Files:**
- Modify: `snap-ui/nuxt.config.ts`
- Create or modify: `snap-ui/app.config.ts`
- Create or modify: `snap-ui/app/assets/css/main.css`
- Modify: `snap-ui/app/app.vue`
- Modify: `snap-ui/app/pages/index.vue`

- [ ] **Step 1: Configure Nuxt UI**

Replace `snap-ui/nuxt.config.ts` with:

```ts
export default defineNuxtConfig({
  compatibilityDate: '2026-04-27',
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
  devtools: { enabled: true },
  nitro: {
    experimental: {
      openAPI: true
    }
  },
  typescript: {
    strict: true,
    typeCheck: true
  },
  ui: {
    colorMode: false,
    theme: {
      colors: ['primary', 'success', 'warning', 'error', 'neutral']
    }
  }
})
```

- [ ] **Step 2: Configure Nuxt UI semantic colors and icons**

Create `snap-ui/app.config.ts`:

```ts
export default defineAppConfig({
  ui: {
    colors: {
      primary: 'wechat',
      success: 'wechat',
      warning: 'amber',
      error: 'risk',
      neutral: 'clean'
    },
    icons: {
      loading: 'i-lucide-loader-circle',
      calendar: 'i-lucide-calendar-days',
      refresh: 'i-lucide-refresh-cw',
      filter: 'i-lucide-list-filter',
      chart: 'i-lucide-chart-no-axes-combined'
    }
  }
})
```

- [ ] **Step 3: Add theme CSS**

Create `snap-ui/app/assets/css/main.css`:

```css
@import "tailwindcss";
@import "@nuxt/ui";

@theme static {
  --font-sans: "Avenir Next", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  --font-mono: "SFMono-Regular", "Menlo", "Consolas", monospace;

  --color-wechat-50: #eefbf4;
  --color-wechat-100: #d7f7e5;
  --color-wechat-200: #aef0cb;
  --color-wechat-300: #76e5aa;
  --color-wechat-400: #35d582;
  --color-wechat-500: #07c160;
  --color-wechat-600: #128c45;
  --color-wechat-700: #126f3a;
  --color-wechat-800: #115832;
  --color-wechat-900: #0f492b;
  --color-wechat-950: #052918;

  --color-clean-50: #f7f8f7;
  --color-clean-100: #eef0ee;
  --color-clean-200: #e6e8e6;
  --color-clean-300: #cdd3ce;
  --color-clean-400: #aab5ad;
  --color-clean-500: #87928b;
  --color-clean-600: #6b756e;
  --color-clean-700: #535d56;
  --color-clean-800: #38433d;
  --color-clean-900: #1f2a24;
  --color-clean-950: #101612;

  --color-risk-50: #fff1f1;
  --color-risk-500: #d64545;
  --color-risk-700: #9f2626;

  --radius-dashboard: 8px;
}

:root {
  color: #1f2a24;
  background: #f7f8f7;
}

html {
  min-height: 100%;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

body {
  min-height: 100%;
  margin: 0;
  background:
    linear-gradient(180deg, rgba(7, 193, 96, 0.045), rgba(247, 248, 247, 0) 240px),
    #f7f8f7;
}

* {
  box-sizing: border-box;
}

button,
input,
select {
  font: inherit;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 4: Wrap app with Nuxt UI app provider**

Replace `snap-ui/app/app.vue` with:

```vue
<template>
  <UApp>
    <NuxtPage />
  </UApp>
</template>
```

- [ ] **Step 5: Add a temporary page shell**

Replace `snap-ui/app/pages/index.vue` with:

```vue
<template>
  <main class="min-h-screen px-4 py-4 text-clean-900 sm:px-6 lg:px-8">
    <section class="mx-auto flex max-w-[1680px] flex-col gap-4">
      <div class="rounded-dashboard border border-clean-200 bg-white p-5 shadow-sm">
        <p class="text-sm text-clean-600">每日快照分析台</p>
        <h1 class="mt-1 text-2xl font-semibold text-clean-900">主线资金优先</h1>
      </div>
    </section>
  </main>
</template>
```

- [ ] **Step 6: Verify build**

Run:

```bash
cd snap-ui
npm run build
```

Expected:

```text
✓ built
```

- [ ] **Step 7: Commit theme baseline**

Run:

```bash
git -C snap-ui add nuxt.config.ts app.config.ts app/app.vue app/assets/css/main.css app/pages/index.vue package.json package-lock.json
git -C snap-ui commit -m "feat: add clean WeChat green app shell"
```

Expected:

```text
[main ...] feat: add clean WeChat green app shell
```

## Task 3: Add Snapshot Scanner And Shared Types

**Files:**
- Create: `snap-ui/app/types/snapshot.ts`
- Create: `snap-ui/server/utils/sourcePath.ts`
- Create: `snap-ui/server/utils/snapshot/scanner.ts`
- Create: `snap-ui/tests/unit/snapshotScanner.test.ts`
- Create: `snap-ui/vitest.config.ts`

- [ ] **Step 1: Add Vitest config**

Create `snap-ui/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'happy-dom',
    globals: true,
    include: ['tests/unit/**/*.test.ts']
  },
  resolve: {
    alias: {
      '~': new URL('./app', import.meta.url).pathname,
      '~~': new URL('.', import.meta.url).pathname
    }
  }
})
```

- [ ] **Step 2: Define shared snapshot types**

Create `snap-ui/app/types/snapshot.ts`:

```ts
export type SnapshotMode = 'frozen' | 'replay'
export type SourceStatus = 'success' | 'degraded' | 'missing' | 'error'

export interface SnapshotRef {
  date: string
  mode: SnapshotMode
  filePath: string
}

export interface SnapshotIndexResponse {
  refs: SnapshotRef[]
  dates: string[]
  modesByDate: Record<string, SnapshotMode[]>
}

export interface DataStatus {
  status: SourceStatus
  message: string
  sourceField?: string
}

export interface MainlineOverview {
  date: string
  currentMainline: string
  secondaryMainline: string
  competitionMainline: string
  stateCode: string
  sectorName: string
  sectorTurnover: number | null
  marketTurnover: number | null
  turnoverSharePct: number | null
  sourceStatus: SourceStatus
  sourceMessage: string
}

export interface MainlineSeriesRow extends MainlineOverview {
  shareChangePct: number | null
}

export interface ObservationPoolStock {
  stockName: string
  stockCode: string
  sourcePool: string
  poolGroup: 'main' | 'secondary'
  currentAction: string
  status: SourceStatus
}

export interface ObservationPoolGroup {
  label: string
  poolGroup: 'main' | 'secondary'
  rows: ObservationPoolStock[]
}

export interface ObservationPoolResponse {
  date: string
  groups: ObservationPoolGroup[]
  status: DataStatus
}

export interface KlineRow {
  date: string
  open: number
  close: number
  low: number
  high: number
  volume: number | null
  dailyChangePct: number | null
  cumulativeChangePct: number | null
}

export interface StockKlineResponse {
  date: string
  stockCode: string
  stockName: string
  source: string
  rows: KlineRow[]
  status: DataStatus
}
```

- [ ] **Step 3: Write failing scanner tests**

Create `snap-ui/tests/unit/snapshotScanner.test.ts`:

```ts
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { describe, expect, it, afterEach } from 'vitest'
import { listSnapshotRefs } from '../../server/utils/snapshot/scanner'

const roots: string[] = []

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), 'snap-ui-'))
  roots.push(root)
  await mkdir(join(root, 'snapshots', 'replay'), { recursive: true })
  return root
}

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

describe('listSnapshotRefs', () => {
  it('lists frozen and replay snapshots in date order', async () => {
    const root = await makeRoot()
    await writeFile(join(root, 'snapshots', '2026-04-27.json'), '{}')
    await writeFile(join(root, 'snapshots', 'replay', '2026-04-24_replay.json'), '{}')
    await writeFile(join(root, 'snapshots', 'notes.txt'), 'ignored')

    const result = await listSnapshotRefs(root)

    expect(result.dates).toEqual(['2026-04-24', '2026-04-27'])
    expect(result.modesByDate).toEqual({
      '2026-04-24': ['replay'],
      '2026-04-27': ['frozen']
    })
    expect(result.refs.map((item) => `${item.date}:${item.mode}`)).toEqual([
      '2026-04-24:replay',
      '2026-04-27:frozen'
    ])
  })
})
```

- [ ] **Step 4: Run the scanner test to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/snapshotScanner.test.ts
```

Expected:

```text
FAIL tests/unit/snapshotScanner.test.ts
Cannot find module '../../server/utils/snapshot/scanner'
```

- [ ] **Step 5: Implement source root resolver**

Create `snap-ui/server/utils/sourcePath.ts`:

```ts
import { resolve } from 'node:path'

export const DAILY_REPORT_ROOT = resolve(process.cwd(), '..')

export function resolveDailyReportPath(...segments: string[]) {
  const resolved = resolve(DAILY_REPORT_ROOT, ...segments)
  if (!resolved.startsWith(DAILY_REPORT_ROOT)) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Path escapes daily report root'
    })
  }
  return resolved
}
```

- [ ] **Step 6: Implement snapshot scanner**

Create `snap-ui/server/utils/snapshot/scanner.ts`:

```ts
import { readdir } from 'node:fs/promises'
import { join } from 'node:path'
import type { SnapshotIndexResponse, SnapshotMode, SnapshotRef } from '../../../app/types/snapshot'
import { DAILY_REPORT_ROOT } from '../sourcePath'

const FROZEN_RE = /^(\d{4}-\d{2}-\d{2})\.json$/
const REPLAY_RE = /^(\d{4}-\d{2}-\d{2})_replay\.json$/

async function readDirSafe(path: string) {
  try {
    return await readdir(path)
  } catch {
    return []
  }
}

function addMode(modesByDate: Record<string, SnapshotMode[]>, date: string, mode: SnapshotMode) {
  const modes = modesByDate[date] || []
  if (!modes.includes(mode)) {
    modes.push(mode)
  }
  modesByDate[date] = modes.sort()
}

export async function listSnapshotRefs(root = DAILY_REPORT_ROOT): Promise<SnapshotIndexResponse> {
  const frozenDir = join(root, 'snapshots')
  const replayDir = join(root, 'snapshots', 'replay')
  const refs: SnapshotRef[] = []
  const modesByDate: Record<string, SnapshotMode[]> = {}

  for (const fileName of await readDirSafe(frozenDir)) {
    const match = fileName.match(FROZEN_RE)
    if (!match) continue
    const date = match[1]
    refs.push({ date, mode: 'frozen', filePath: join(frozenDir, fileName) })
    addMode(modesByDate, date, 'frozen')
  }

  for (const fileName of await readDirSafe(replayDir)) {
    const match = fileName.match(REPLAY_RE)
    if (!match) continue
    const date = match[1]
    refs.push({ date, mode: 'replay', filePath: join(replayDir, fileName) })
    addMode(modesByDate, date, 'replay')
  }

  refs.sort((a, b) => a.date.localeCompare(b.date) || a.mode.localeCompare(b.mode))

  return {
    refs,
    dates: Object.keys(modesByDate).sort(),
    modesByDate
  }
}
```

- [ ] **Step 7: Run scanner test to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/snapshotScanner.test.ts
```

Expected:

```text
PASS tests/unit/snapshotScanner.test.ts
```

- [ ] **Step 8: Commit scanner and types**

Run:

```bash
git -C snap-ui add app/types/snapshot.ts server/utils/sourcePath.ts server/utils/snapshot/scanner.ts tests/unit/snapshotScanner.test.ts vitest.config.ts package.json package-lock.json
git -C snap-ui commit -m "feat: add snapshot scanner"
```

Expected:

```text
[main ...] feat: add snapshot scanner
```

## Task 4: Add Mainline Series Adapter

**Files:**
- Create: `snap-ui/server/utils/snapshot/loadSnapshot.ts`
- Create: `snap-ui/server/utils/snapshot/mainlineAdapter.ts`
- Create: `snap-ui/tests/unit/mainlineAdapter.test.ts`

- [ ] **Step 1: Write failing mainline adapter tests**

Create `snap-ui/tests/unit/mainlineAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildMainlineOverview, buildMainlineSeries, parseAmountYi, parsePct } from '../../server/utils/snapshot/mainlineAdapter'

describe('mainlineAdapter', () => {
  it('parses Chinese amount and percent strings', () => {
    expect(parseAmountYi('3007.99亿')).toBe(3007.99)
    expect(parseAmountYi('25894.51亿')).toBe(25894.51)
    expect(parsePct('11.6%')).toBe(11.6)
    expect(parsePct('待累计')).toBeNull()
  })

  it('builds overview from preferred snapshot fields', () => {
    const overview = buildMainlineOverview({
      current_sector_turnover_snapshot: {
        date: '2026-04-27',
        sector_name: '半导体',
        sector_turnover: 3007.99,
        total_turnover: 25894.51,
        turnover_share_pct: 11.62,
        source_status: 'success'
      },
      current_mainline_history_record: {
        primary_mainline: '半导体',
        secondary_mainline: '电力',
        competition_mainline: '消费电子',
        state_code: 'contract'
      }
    })

    expect(overview.currentMainline).toBe('半导体')
    expect(overview.secondaryMainline).toBe('电力')
    expect(overview.competitionMainline).toBe('消费电子')
    expect(overview.sectorTurnover).toBe(3007.99)
    expect(overview.marketTurnover).toBe(25894.51)
    expect(overview.turnoverSharePct).toBe(11.62)
    expect(overview.sourceStatus).toBe('success')
  })

  it('computes share change across sorted rows', () => {
    const rows = buildMainlineSeries([
      {
        current_sector_turnover_snapshot: {
          date: '2026-04-24',
          sector_name: '半导体',
          sector_turnover: 3007.99,
          total_turnover: 26414.92,
          turnover_share_pct: 11.39,
          source_status: 'success'
        },
        current_mainline_history_record: { primary_mainline: '半导体' }
      },
      {
        current_sector_turnover_snapshot: {
          date: '2026-04-27',
          sector_name: '半导体',
          sector_turnover: 3007.99,
          total_turnover: 25894.51,
          turnover_share_pct: 11.62,
          source_status: 'success'
        },
        current_mainline_history_record: { primary_mainline: '半导体' }
      }
    ])

    expect(rows.map((row) => row.date)).toEqual(['2026-04-24', '2026-04-27'])
    expect(rows[0].shareChangePct).toBeNull()
    expect(rows[1].shareChangePct).toBeCloseTo(0.23, 2)
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/mainlineAdapter.test.ts
```

Expected:

```text
FAIL tests/unit/mainlineAdapter.test.ts
Cannot find module '../../server/utils/snapshot/mainlineAdapter'
```

- [ ] **Step 3: Add snapshot JSON loader**

Create `snap-ui/server/utils/snapshot/loadSnapshot.ts`:

```ts
import { readFile } from 'node:fs/promises'

export async function loadSnapshotFile(filePath: string): Promise<Record<string, unknown>> {
  const raw = await readFile(filePath, 'utf-8')
  const parsed = JSON.parse(raw)
  if (parsed && typeof parsed === 'object' && 'data' in parsed) {
    return (parsed as { data: Record<string, unknown> }).data || {}
  }
  return parsed && typeof parsed === 'object' ? parsed as Record<string, unknown> : {}
}
```

- [ ] **Step 4: Implement mainline adapter**

Create `snap-ui/server/utils/snapshot/mainlineAdapter.ts`:

```ts
import type { MainlineOverview, MainlineSeriesRow, SourceStatus } from '../../../app/types/snapshot'

type AnyRecord = Record<string, any>

export function parseAmountYi(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const text = String(value ?? '').replace('亿', '').trim()
  if (!text || text === '-' || text === '数据暂缺') return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

export function parsePct(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const text = String(value ?? '').replace('%', '').replace('pct', '').trim()
  if (!text || text === '-' || text === '待累计') return null
  const parsed = Number(text)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeStatus(value: unknown): SourceStatus {
  const text = String(value || '').trim()
  if (text === 'success') return 'success'
  if (text === 'degraded') return 'degraded'
  if (text === 'error') return 'error'
  return 'missing'
}

function fromFallbackRow(snapshot: AnyRecord): Partial<MainlineOverview> {
  const rows = snapshot?.mainline_turnover_summary?.turnover_share_trend_rows || []
  const last = Array.isArray(rows) ? rows.at(-1) : undefined
  if (!last) return {}
  return {
    date: String(last.date || ''),
    sectorName: String(last.cycle_mainline || ''),
    currentMainline: String(last.cycle_mainline || ''),
    sectorTurnover: parseAmountYi(last.mainline_turnover),
    marketTurnover: parseAmountYi(last.market_turnover),
    turnoverSharePct: parsePct(last.share)
  }
}

export function buildMainlineOverview(snapshot: AnyRecord): MainlineOverview {
  const sector = snapshot.current_sector_turnover_snapshot || {}
  const history = snapshot.current_mainline_history_record || {}
  const fallback = fromFallbackRow(snapshot)
  const date = String(sector.date || history.date || fallback.date || snapshot.target_date || '')
  const sectorName = String(sector.sector_name || fallback.sectorName || history.primary_mainline || '')
  const sourceStatus = normalizeStatus(sector.source_status || (sectorName ? 'success' : 'missing'))

  return {
    date,
    currentMainline: String(history.primary_mainline || history.leading_line || fallback.currentMainline || sectorName || ''),
    secondaryMainline: String(history.secondary_mainline || ''),
    competitionMainline: String(history.competition_mainline || ''),
    stateCode: String(history.state_code || ''),
    sectorName,
    sectorTurnover: parseAmountYi(sector.sector_turnover ?? fallback.sectorTurnover),
    marketTurnover: parseAmountYi(sector.total_turnover ?? fallback.marketTurnover),
    turnoverSharePct: parsePct(sector.turnover_share_pct ?? fallback.turnoverSharePct),
    sourceStatus,
    sourceMessage: sourceStatus === 'success' ? '成交额字段可用' : '快照缺少成交额字段'
  }
}

export function buildMainlineSeries(snapshots: AnyRecord[]): MainlineSeriesRow[] {
  const rows = snapshots
    .map((snapshot) => buildMainlineOverview(snapshot))
    .filter((row) => row.date)
    .sort((a, b) => a.date.localeCompare(b.date))

  let previousShare: number | null = null
  return rows.map((row) => {
    const shareChangePct =
      row.turnoverSharePct !== null && previousShare !== null
        ? Number((row.turnoverSharePct - previousShare).toFixed(2))
        : null
    if (row.turnoverSharePct !== null) {
      previousShare = row.turnoverSharePct
    }
    return { ...row, shareChangePct }
  })
}
```

- [ ] **Step 5: Run mainline tests to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/mainlineAdapter.test.ts
```

Expected:

```text
PASS tests/unit/mainlineAdapter.test.ts
```

- [ ] **Step 6: Commit mainline adapter**

Run:

```bash
git -C snap-ui add server/utils/snapshot/loadSnapshot.ts server/utils/snapshot/mainlineAdapter.ts tests/unit/mainlineAdapter.test.ts
git -C snap-ui commit -m "feat: normalize mainline turnover snapshots"
```

Expected:

```text
[main ...] feat: normalize mainline turnover snapshots
```

## Task 5: Add Observation Pool Adapter

**Files:**
- Create: `snap-ui/server/utils/snapshot/observationPoolAdapter.ts`
- Create: `snap-ui/tests/unit/observationPoolAdapter.test.ts`

- [ ] **Step 1: Write failing observation pool tests**

Create `snap-ui/tests/unit/observationPoolAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildObservationPool } from '../../server/utils/snapshot/observationPoolAdapter'

describe('buildObservationPool', () => {
  it('groups appendix observation rows and dedupes by stock code', () => {
    const result = buildObservationPool('2026-04-27', {
      appendix_c: {
        current_stock_monitoring_pool: [
          { stock_name: '圣阳股份', stock_code: '002580', source_pool: '主线核心', current_action: '需看明日竞价强弱' },
          { stock_name: '圣阳股份', stock_code: '002580', source_pool: '普通观察', current_action: '继续跟踪' },
          { stock_name: '深圳华强', stock_code: '000062', source_pool: '普通观察', current_action: '继续跟踪' }
        ]
      }
    })

    expect(result.status.status).toBe('success')
    expect(result.groups.map((group) => group.label)).toEqual(['主线核心', '普通观察'])
    expect(result.groups[0].poolGroup).toBe('main')
    expect(result.groups[0].rows[0].stockName).toBe('圣阳股份')
    expect(result.groups[1].poolGroup).toBe('secondary')
    expect(result.groups[1].rows).toHaveLength(1)
  })

  it('returns a clear empty state when no pool exists', () => {
    const result = buildObservationPool('2026-04-27', {})

    expect(result.groups).toEqual([])
    expect(result.status).toEqual({
      status: 'missing',
      message: '该日期无观察池',
      sourceField: 'data.appendix_c.current_stock_monitoring_pool'
    })
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/observationPoolAdapter.test.ts
```

Expected:

```text
FAIL tests/unit/observationPoolAdapter.test.ts
Cannot find module '../../server/utils/snapshot/observationPoolAdapter'
```

- [ ] **Step 3: Implement observation pool adapter**

Create `snap-ui/server/utils/snapshot/observationPoolAdapter.ts`:

```ts
import type { ObservationPoolGroup, ObservationPoolResponse, ObservationPoolStock } from '../../../app/types/snapshot'

type AnyRecord = Record<string, any>

const GROUP_ORDER = ['主线核心', '主线备选', '跨线观察', '20cm 侧翼观察', '普通观察']

function normalizeCode(value: unknown) {
  const code = String(value || '').replace(/\D/g, '')
  return code.length === 6 ? code : ''
}

function poolGroup(sourcePool: string): 'main' | 'secondary' {
  return sourcePool === '主线核心' || sourcePool === '主线备选' ? 'main' : 'secondary'
}

function normalizeRow(item: AnyRecord): ObservationPoolStock | null {
  const stockCode = normalizeCode(item.stock_code || item.code)
  const stockName = String(item.stock_name || item.name || '').trim()
  if (!stockCode || !stockName) return null
  const sourcePool = String(item.source_pool || item.sourcePool || '普通观察').trim() || '普通观察'
  return {
    stockName,
    stockCode,
    sourcePool,
    poolGroup: poolGroup(sourcePool),
    currentAction: String(item.current_action || item.current_assessment || item.action || '继续跟踪').trim(),
    status: 'success'
  }
}

export function buildObservationPool(date: string, snapshot: AnyRecord): ObservationPoolResponse {
  const sourceRows = snapshot?.appendix_c?.current_stock_monitoring_pool || []
  const rows = Array.isArray(sourceRows) ? sourceRows.map(normalizeRow).filter(Boolean) as ObservationPoolStock[] : []
  const seen = new Set<string>()
  const deduped: ObservationPoolStock[] = []

  for (const row of rows) {
    if (seen.has(row.stockCode)) continue
    seen.add(row.stockCode)
    deduped.push(row)
  }

  if (!deduped.length) {
    return {
      date,
      groups: [],
      status: {
        status: 'missing',
        message: '该日期无观察池',
        sourceField: 'data.appendix_c.current_stock_monitoring_pool'
      }
    }
  }

  const grouped = new Map<string, ObservationPoolStock[]>()
  for (const row of deduped) {
    grouped.set(row.sourcePool, [...(grouped.get(row.sourcePool) || []), row])
  }

  const groups: ObservationPoolGroup[] = [...grouped.entries()]
    .sort(([a], [b]) => {
      const ai = GROUP_ORDER.indexOf(a)
      const bi = GROUP_ORDER.indexOf(b)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
    .map(([label, groupRows]) => ({
      label,
      poolGroup: poolGroup(label),
      rows: groupRows
    }))

  return {
    date,
    groups,
    status: {
      status: 'success',
      message: '观察池字段可用',
      sourceField: 'data.appendix_c.current_stock_monitoring_pool'
    }
  }
}
```

- [ ] **Step 4: Run observation pool tests to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/observationPoolAdapter.test.ts
```

Expected:

```text
PASS tests/unit/observationPoolAdapter.test.ts
```

- [ ] **Step 5: Commit observation pool adapter**

Run:

```bash
git -C snap-ui add server/utils/snapshot/observationPoolAdapter.ts tests/unit/observationPoolAdapter.test.ts
git -C snap-ui commit -m "feat: normalize observation pool snapshots"
```

Expected:

```text
[main ...] feat: normalize observation pool snapshots
```

## Task 6: Add K-Line Adapter

**Files:**
- Create: `snap-ui/server/utils/snapshot/klineAdapter.ts`
- Create: `snap-ui/tests/unit/klineAdapter.test.ts`

- [ ] **Step 1: Write failing K-line adapter tests**

Create `snap-ui/tests/unit/klineAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildStockKline } from '../../server/utils/snapshot/klineAdapter'

describe('buildStockKline', () => {
  it('uses entry cycle day_rows when the selected stock is present', () => {
    const result = buildStockKline('2026-04-27', '002975', {
      entry_cycle_calibration: {
        cases: [
          {
            name: '博杰股份',
            code: '002975',
            day_rows: [
              { date: '2026-04-24', open: 112.3, high: 119.5, low: 112.3, close: 115.73, daily_change_pct: 2.77, cum_change_pct: 33.18 },
              { date: '2026-04-27', open: 112.3, high: 119.5, low: 112.3, close: 115.73, daily_change_pct: 0, cum_change_pct: 33.18 }
            ]
          }
        ]
      }
    })

    expect(result.stockName).toBe('博杰股份')
    expect(result.source).toBe('entry_cycle_calibration.cases[].day_rows')
    expect(result.rows).toHaveLength(2)
    expect(result.rows[0]).toMatchObject({ date: '2026-04-24', open: 112.3, close: 115.73 })
  })

  it('returns explicit empty state when rows are missing', () => {
    const result = buildStockKline('2026-04-27', '002580', {})

    expect(result.rows).toEqual([])
    expect(result.status).toEqual({
      status: 'missing',
      message: '暂无 K 线数据',
      sourceField: 'entry_cycle_calibration.cases[].day_rows'
    })
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/klineAdapter.test.ts
```

Expected:

```text
FAIL tests/unit/klineAdapter.test.ts
Cannot find module '../../server/utils/snapshot/klineAdapter'
```

- [ ] **Step 3: Implement K-line adapter**

Create `snap-ui/server/utils/snapshot/klineAdapter.ts`:

```ts
import type { KlineRow, StockKlineResponse } from '../../../app/types/snapshot'

type AnyRecord = Record<string, any>

function normalizeCode(value: unknown) {
  const code = String(value || '').replace(/\D/g, '')
  return code.length === 6 ? code : ''
}

function toNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeDayRow(row: AnyRecord): KlineRow | null {
  const date = String(row.date || '').trim()
  const open = toNumber(row.open)
  const close = toNumber(row.close)
  const low = toNumber(row.low)
  const high = toNumber(row.high)
  if (!date || open === null || close === null || low === null || high === null) return null
  return {
    date,
    open,
    close,
    low,
    high,
    volume: toNumber(row.volume),
    dailyChangePct: toNumber(row.daily_change_pct ?? row.dailyChangePct),
    cumulativeChangePct: toNumber(row.cum_change_pct ?? row.cumulativeChangePct)
  }
}

export function buildStockKline(date: string, code: string, snapshot: AnyRecord): StockKlineResponse {
  const normalizedCode = normalizeCode(code)
  const cases = snapshot?.entry_cycle_calibration?.cases || []
  const matchedCase = Array.isArray(cases)
    ? cases.find((item: AnyRecord) => normalizeCode(item.code || item.stock_code) === normalizedCode)
    : undefined
  const dayRows = matchedCase?.day_rows

  if (Array.isArray(dayRows) && dayRows.length) {
    return {
      date,
      stockCode: normalizedCode,
      stockName: String(matchedCase.name || matchedCase.stock_name || ''),
      source: 'entry_cycle_calibration.cases[].day_rows',
      rows: dayRows.map(normalizeDayRow).filter(Boolean) as KlineRow[],
      status: {
        status: 'success',
        message: 'K 线字段可用',
        sourceField: 'entry_cycle_calibration.cases[].day_rows'
      }
    }
  }

  return {
    date,
    stockCode: normalizedCode,
    stockName: '',
    source: '',
    rows: [],
    status: {
      status: 'missing',
      message: '暂无 K 线数据',
      sourceField: 'entry_cycle_calibration.cases[].day_rows'
    }
  }
}
```

- [ ] **Step 4: Run K-line tests to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/klineAdapter.test.ts
```

Expected:

```text
PASS tests/unit/klineAdapter.test.ts
```

- [ ] **Step 5: Commit K-line adapter**

Run:

```bash
git -C snap-ui add server/utils/snapshot/klineAdapter.ts tests/unit/klineAdapter.test.ts
git -C snap-ui commit -m "feat: normalize stock kline rows"
```

Expected:

```text
[main ...] feat: normalize stock kline rows
```

## Task 7: Add Nuxt Server API Routes

**Files:**
- Create: `snap-ui/server/utils/snapshot/request.ts`
- Create: `snap-ui/server/api/snapshots/index.get.ts`
- Create: `snap-ui/server/api/snapshots/[date]/overview.get.ts`
- Create: `snap-ui/server/api/mainline-series.get.ts`
- Create: `snap-ui/server/api/observation-pool.get.ts`
- Create: `snap-ui/server/api/observation-pool/[code]/kline.get.ts`

- [ ] **Step 1: Add request helpers**

Create `snap-ui/server/utils/snapshot/request.ts`:

```ts
import { join } from 'node:path'
import { z } from 'zod'
import type { SnapshotMode } from '../../../app/types/snapshot'
import { DAILY_REPORT_ROOT } from '../sourcePath'

export const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
export const modeSchema = z.enum(['frozen', 'replay']).default('frozen')
export const codeSchema = z.string().regex(/^\d{6}$/)

export function snapshotPathFor(date: string, mode: SnapshotMode) {
  dateSchema.parse(date)
  if (mode === 'replay') {
    return join(DAILY_REPORT_ROOT, 'snapshots', 'replay', `${date}_replay.json`)
  }
  return join(DAILY_REPORT_ROOT, 'snapshots', `${date}.json`)
}
```

- [ ] **Step 2: Add snapshot index endpoint**

Create `snap-ui/server/api/snapshots/index.get.ts`:

```ts
import { listSnapshotRefs } from '../../utils/snapshot/scanner'

export default defineEventHandler(async () => {
  return await listSnapshotRefs()
})
```

- [ ] **Step 3: Add overview endpoint**

Create `snap-ui/server/api/snapshots/[date]/overview.get.ts`:

```ts
import { getRouterParam, getQuery } from 'h3'
import { buildMainlineOverview } from '../../../utils/snapshot/mainlineAdapter'
import { loadSnapshotFile } from '../../../utils/snapshot/loadSnapshot'
import { dateSchema, modeSchema, snapshotPathFor } from '../../../utils/snapshot/request'

export default defineEventHandler(async (event) => {
  const date = dateSchema.parse(getRouterParam(event, 'date'))
  const mode = modeSchema.parse(getQuery(event).mode || 'frozen')
  const snapshot = await loadSnapshotFile(snapshotPathFor(date, mode))
  return buildMainlineOverview(snapshot)
})
```

- [ ] **Step 4: Add mainline series endpoint**

Create `snap-ui/server/api/mainline-series.get.ts`:

```ts
import { getQuery } from 'h3'
import { listSnapshotRefs } from '../utils/snapshot/scanner'
import { loadSnapshotFile } from '../utils/snapshot/loadSnapshot'
import { buildMainlineSeries } from '../utils/snapshot/mainlineAdapter'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const mode = String(query.mode || 'auto')
  const from = String(query.from || '')
  const to = String(query.to || '')
  const index = await listSnapshotRefs()
  const selectedRefs = index.refs.filter((ref) => {
    if (mode !== 'auto' && ref.mode !== mode) return false
    if (from && ref.date < from) return false
    if (to && ref.date > to) return false
    return true
  })
  const byDate = new Map<string, typeof selectedRefs[number]>()
  for (const ref of selectedRefs) {
    const existing = byDate.get(ref.date)
    if (!existing || existing.mode === 'frozen') {
      byDate.set(ref.date, ref)
    }
  }
  const snapshots = await Promise.all([...byDate.values()].map((ref) => loadSnapshotFile(ref.filePath)))
  return { rows: buildMainlineSeries(snapshots) }
})
```

- [ ] **Step 5: Add observation pool endpoint**

Create `snap-ui/server/api/observation-pool.get.ts`:

```ts
import { getQuery } from 'h3'
import { loadSnapshotFile } from '../utils/snapshot/loadSnapshot'
import { buildObservationPool } from '../utils/snapshot/observationPoolAdapter'
import { dateSchema, modeSchema, snapshotPathFor } from '../utils/snapshot/request'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const date = dateSchema.parse(query.date)
  const mode = modeSchema.parse(query.mode || 'frozen')
  const snapshot = await loadSnapshotFile(snapshotPathFor(date, mode))
  return buildObservationPool(date, snapshot)
})
```

- [ ] **Step 6: Add K-line endpoint**

Create `snap-ui/server/api/observation-pool/[code]/kline.get.ts`:

```ts
import { getRouterParam, getQuery } from 'h3'
import { loadSnapshotFile } from '../../../utils/snapshot/loadSnapshot'
import { buildStockKline } from '../../../utils/snapshot/klineAdapter'
import { codeSchema, dateSchema, modeSchema, snapshotPathFor } from '../../../utils/snapshot/request'

export default defineEventHandler(async (event) => {
  const code = codeSchema.parse(getRouterParam(event, 'code'))
  const query = getQuery(event)
  const date = dateSchema.parse(query.date)
  const mode = modeSchema.parse(query.mode || 'frozen')
  const snapshot = await loadSnapshotFile(snapshotPathFor(date, mode))
  return buildStockKline(date, code, snapshot)
})
```

- [ ] **Step 7: Verify API build**

Run:

```bash
cd snap-ui
npm run build
```

Expected:

```text
✓ built
```

- [ ] **Step 8: Verify API manually against local snapshots**

Run:

```bash
cd snap-ui
npm run dev
```

In another terminal run:

```bash
curl -s http://127.0.0.1:3040/api/snapshots | node -e "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const j=JSON.parse(s); console.log(j.dates.includes('2026-04-27'))})"
curl -s 'http://127.0.0.1:3040/api/snapshots/2026-04-27/overview?mode=frozen' | node -e "let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const j=JSON.parse(s); console.log(j.currentMainline)})"
```

Expected:

```text
true
半导体
```

- [ ] **Step 9: Commit API routes**

Run:

```bash
git -C snap-ui add server
git -C snap-ui commit -m "feat: expose snapshot analysis APIs"
```

Expected:

```text
[main ...] feat: expose snapshot analysis APIs
```

## Task 8: Add ECharts Option Builders

**Files:**
- Create: `snap-ui/app/utils/charts/mainlineOptions.ts`
- Create: `snap-ui/app/utils/charts/klineOptions.ts`
- Create: `snap-ui/tests/unit/chartOptions.test.ts`

- [ ] **Step 1: Write failing chart option tests**

Create `snap-ui/tests/unit/chartOptions.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildMainlineOptions } from '../../app/utils/charts/mainlineOptions'
import { buildKlineOptions } from '../../app/utils/charts/klineOptions'

describe('chart option builders', () => {
  it('sets every mainline line series to smooth', () => {
    const options = buildMainlineOptions([
      { date: '2026-04-24', currentMainline: '半导体', secondaryMainline: '', competitionMainline: '', stateCode: '', sectorName: '半导体', sectorTurnover: 3007.99, marketTurnover: 26414.92, turnoverSharePct: 11.39, sourceStatus: 'success', sourceMessage: '', shareChangePct: null },
      { date: '2026-04-27', currentMainline: '半导体', secondaryMainline: '', competitionMainline: '', stateCode: '', sectorName: '半导体', sectorTurnover: 3007.99, marketTurnover: 25894.51, turnoverSharePct: 11.62, sourceStatus: 'success', sourceMessage: '', shareChangePct: 0.23 }
    ])

    const series = options.series as Array<{ type: string; smooth?: boolean }>
    expect(series.filter((item) => item.type === 'line').every((item) => item.smooth === true)).toBe(true)
  })

  it('builds candlestick and volume bar series', () => {
    const options = buildKlineOptions([
      { date: '2026-04-27', open: 10, close: 11, low: 9.8, high: 11.2, volume: 1200, dailyChangePct: 2, cumulativeChangePct: 5 }
    ])

    const series = options.series as Array<{ type: string }>
    expect(series.map((item) => item.type)).toEqual(['candlestick', 'bar'])
  })
})
```

- [ ] **Step 2: Run chart option tests to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/chartOptions.test.ts
```

Expected:

```text
FAIL tests/unit/chartOptions.test.ts
Cannot find module '../../app/utils/charts/mainlineOptions'
```

- [ ] **Step 3: Implement mainline option builder**

Create `snap-ui/app/utils/charts/mainlineOptions.ts`:

```ts
import type { EChartsOption } from 'echarts'
import type { MainlineSeriesRow } from '../../types/snapshot'

export function buildMainlineOptions(rows: MainlineSeriesRow[]): EChartsOption {
  const dates = rows.map((row) => row.date)
  return {
    color: ['#07C160', '#AAB5AD', '#128C45'],
    grid: { left: 48, right: 54, top: 40, bottom: 48 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { top: 4, right: 8, textStyle: { color: '#6B756E' } },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#CDD3CE' } } },
    yAxis: [
      { type: 'value', name: '成交额(亿)', axisLine: { lineStyle: { color: '#AAB5AD' } }, splitLine: { lineStyle: { color: '#EEF0EE' } } },
      { type: 'value', name: '占比%', axisLabel: { formatter: '{value}%' }, splitLine: { show: false } }
    ],
    series: [
      {
        name: '主线成交额',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: rows.map((row) => row.sectorTurnover)
      },
      {
        name: '两市成交额',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: rows.map((row) => row.marketTurnover)
      },
      {
        name: '主线成交额占比',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        showSymbol: true,
        symbolSize: 6,
        areaStyle: { opacity: 0.08 },
        data: rows.map((row) => row.turnoverSharePct)
      }
    ]
  }
}
```

- [ ] **Step 4: Implement K-line option builder**

Create `snap-ui/app/utils/charts/klineOptions.ts`:

```ts
import type { EChartsOption } from 'echarts'
import type { KlineRow } from '../../types/snapshot'

export function buildKlineOptions(rows: KlineRow[]): EChartsOption {
  const dates = rows.map((row) => row.date)
  const candleData = rows.map((row) => [row.open, row.close, row.low, row.high])
  const volumeData = rows.map((row) => row.volume || 0)

  return {
    animation: true,
    color: ['#D64545', '#128C45'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 48, right: 24, top: 32, height: '58%' },
      { left: 48, right: 24, bottom: 36, height: '18%' }
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { lineStyle: { color: '#CDD3CE' } } },
      { type: 'category', data: dates, gridIndex: 1, scale: true, boundaryGap: false, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#CDD3CE' } } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: '#EEF0EE' } } },
      { scale: true, gridIndex: 1, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 4, height: 18 }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candleData,
        itemStyle: {
          color: '#D64545',
          color0: '#128C45',
          borderColor: '#D64545',
          borderColor0: '#128C45'
        }
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: { color: '#AAB5AD' },
        data: volumeData
      }
    ]
  }
}
```

- [ ] **Step 5: Run chart option tests to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/chartOptions.test.ts
```

Expected:

```text
PASS tests/unit/chartOptions.test.ts
```

- [ ] **Step 6: Commit chart option builders**

Run:

```bash
git -C snap-ui add app/utils/charts tests/unit/chartOptions.test.ts
git -C snap-ui commit -m "feat: add dashboard chart options"
```

Expected:

```text
[main ...] feat: add dashboard chart options
```

## Task 9: Add Dashboard State Composable

**Files:**
- Create: `snap-ui/app/composables/useSnapshotDashboard.ts`
- Create: `snap-ui/tests/unit/dashboardState.test.ts`

- [ ] **Step 1: Write failing pure-state tests**

Create `snap-ui/tests/unit/dashboardState.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { pickDefaultStockCode, rangeToFromDate } from '../../app/composables/useSnapshotDashboard'

describe('dashboard state helpers', () => {
  it('picks the first stock from the first non-empty group', () => {
    expect(pickDefaultStockCode([
      { label: '主线核心', poolGroup: 'main', rows: [{ stockName: '圣阳股份', stockCode: '002580', sourcePool: '主线核心', poolGroup: 'main', currentAction: '观察', status: 'success' }] }
    ])).toBe('002580')
  })

  it('converts range keys to a from date using available dates', () => {
    expect(rangeToFromDate('5d', ['2026-04-20', '2026-04-21', '2026-04-22', '2026-04-23', '2026-04-24', '2026-04-27'])).toBe('2026-04-21')
    expect(rangeToFromDate('all', ['2026-04-20', '2026-04-21'])).toBe('')
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/dashboardState.test.ts
```

Expected:

```text
FAIL tests/unit/dashboardState.test.ts
Cannot find module '../../app/composables/useSnapshotDashboard'
```

- [ ] **Step 3: Implement dashboard composable**

Create `snap-ui/app/composables/useSnapshotDashboard.ts`:

```ts
import type { ObservationPoolGroup, SnapshotIndexResponse, SnapshotMode } from '../types/snapshot'

export type RangeKey = '5d' | '10d' | 'all'

export function rangeToFromDate(range: RangeKey, dates: string[]) {
  if (range === 'all') return ''
  const size = range === '5d' ? 5 : 10
  const sorted = [...dates].sort()
  return sorted.length > size ? sorted[sorted.length - size] : sorted[0] || ''
}

export function pickDefaultStockCode(groups: ObservationPoolGroup[]) {
  for (const group of groups) {
    const first = group.rows[0]
    if (first?.stockCode) return first.stockCode
  }
  return ''
}

export function useSnapshotDashboard() {
  const range = ref<RangeKey>('5d')
  const selectedDate = ref('')
  const mode = ref<SnapshotMode>('frozen')
  const poolFilter = ref('全部')
  const selectedStockCode = ref('')

  const snapshots = useFetch<SnapshotIndexResponse>('/api/snapshots', { default: () => ({ refs: [], dates: [], modesByDate: {} }) })

  watchEffect(() => {
    const dates = snapshots.data.value?.dates || []
    if (!selectedDate.value && dates.length) {
      selectedDate.value = dates[dates.length - 1]
    }
  })

  const fromDate = computed(() => rangeToFromDate(range.value, snapshots.data.value?.dates || []))
  const mainlineUrl = computed(() => `/api/mainline-series?mode=auto${fromDate.value ? `&from=${fromDate.value}` : ''}${selectedDate.value ? `&to=${selectedDate.value}` : ''}`)
  const overviewUrl = computed(() => selectedDate.value ? `/api/snapshots/${selectedDate.value}/overview?mode=${mode.value}` : null)
  const poolUrl = computed(() => selectedDate.value ? `/api/observation-pool?date=${selectedDate.value}&mode=${mode.value}` : null)
  const klineUrl = computed(() => selectedDate.value && selectedStockCode.value ? `/api/observation-pool/${selectedStockCode.value}/kline?date=${selectedDate.value}&mode=${mode.value}` : null)

  const mainlineSeries = useFetch(mainlineUrl, { watch: [mainlineUrl], default: () => ({ rows: [] }) })
  const overview = useFetch(overviewUrl, { watch: [overviewUrl] })
  const pool = useFetch(poolUrl, { watch: [poolUrl] })
  const kline = useFetch(klineUrl, { watch: [klineUrl] })

  watchEffect(() => {
    const groups = (pool.data.value as any)?.groups || []
    if (!selectedStockCode.value) {
      selectedStockCode.value = pickDefaultStockCode(groups)
    }
  })

  return {
    range,
    selectedDate,
    mode,
    poolFilter,
    selectedStockCode,
    snapshots,
    mainlineSeries,
    overview,
    pool,
    kline
  }
}
```

- [ ] **Step 4: Run state tests to verify pass**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/dashboardState.test.ts
```

Expected:

```text
PASS tests/unit/dashboardState.test.ts
```

- [ ] **Step 5: Commit dashboard state**

Run:

```bash
git -C snap-ui add app/composables/useSnapshotDashboard.ts tests/unit/dashboardState.test.ts
git -C snap-ui commit -m "feat: add dashboard state composable"
```

Expected:

```text
[main ...] feat: add dashboard state composable
```

## Task 10: Build Mainline Funding UI

**Files:**
- Create: `snap-ui/app/components/MainlineFundingPanel.vue`
- Create: `snap-ui/app/components/MainlineStateStrip.vue`
- Create: `snap-ui/app/components/DataStatusBadge.vue`
- Modify: `snap-ui/app/pages/index.vue`

- [ ] **Step 1: Create data status badge**

Create `snap-ui/app/components/DataStatusBadge.vue`:

```vue
<script setup lang="ts">
import type { SourceStatus } from '../types/snapshot'

const props = defineProps<{
  status?: SourceStatus
  message?: string
}>()

const color = computed(() => {
  if (props.status === 'success') return 'success'
  if (props.status === 'degraded') return 'warning'
  if (props.status === 'error') return 'error'
  return 'neutral'
})
</script>

<template>
  <UBadge :color="color" variant="soft" size="sm">
    {{ message || '数据状态未知' }}
  </UBadge>
</template>
```

- [ ] **Step 2: Create mainline state strip**

Create `snap-ui/app/components/MainlineStateStrip.vue`:

```vue
<script setup lang="ts">
import type { MainlineOverview } from '../types/snapshot'

defineProps<{
  overview?: MainlineOverview | null
}>()
</script>

<template>
  <div class="grid gap-2 border-t border-clean-200 pt-3 text-sm sm:grid-cols-5">
    <div>
      <p class="text-xs text-clean-500">周期主线</p>
      <p class="font-medium text-clean-900">{{ overview?.currentMainline || '-' }}</p>
    </div>
    <div>
      <p class="text-xs text-clean-500">次强 / 竞争</p>
      <p class="font-medium text-clean-900">{{ overview?.secondaryMainline || '-' }} / {{ overview?.competitionMainline || '-' }}</p>
    </div>
    <div>
      <p class="text-xs text-clean-500">成交额</p>
      <p class="font-medium text-clean-900">{{ overview?.sectorTurnover ?? '-' }} 亿</p>
    </div>
    <div>
      <p class="text-xs text-clean-500">占比</p>
      <p class="font-medium text-wechat-700">{{ overview?.turnoverSharePct ?? '-' }}%</p>
    </div>
    <div class="flex items-end">
      <DataStatusBadge :status="overview?.sourceStatus" :message="overview?.sourceMessage" />
    </div>
  </div>
</template>
```

- [ ] **Step 3: Create mainline funding panel**

Create `snap-ui/app/components/MainlineFundingPanel.vue`:

```vue
<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import type { MainlineOverview, MainlineSeriesRow } from '../types/snapshot'
import { buildMainlineOptions } from '../utils/charts/mainlineOptions'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

const props = defineProps<{
  rows: MainlineSeriesRow[]
  overview?: MainlineOverview | null
  loading?: boolean
}>()

const options = computed(() => buildMainlineOptions(props.rows || []))
</script>

<template>
  <section class="rounded-dashboard border border-clean-200 bg-white p-4 shadow-sm">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p class="text-xs font-medium text-wechat-700">主线资金</p>
        <h2 class="text-xl font-semibold text-clean-900">主线成交额占比</h2>
      </div>
      <div class="grid grid-cols-2 gap-2 text-right sm:grid-cols-4">
        <div>
          <p class="text-xs text-clean-500">当前主线</p>
          <p class="text-sm font-semibold text-clean-900">{{ overview?.currentMainline || '-' }}</p>
        </div>
        <div>
          <p class="text-xs text-clean-500">占比</p>
          <p class="text-sm font-semibold text-wechat-700">{{ overview?.turnoverSharePct ?? '-' }}%</p>
        </div>
        <div>
          <p class="text-xs text-clean-500">状态</p>
          <p class="text-sm font-semibold text-clean-900">{{ overview?.stateCode || '-' }}</p>
        </div>
        <div>
          <p class="text-xs text-clean-500">日期</p>
          <p class="text-sm font-semibold text-clean-900">{{ overview?.date || '-' }}</p>
        </div>
      </div>
    </div>

    <USkeleton v-if="loading" class="mt-4 h-[420px] w-full" />
    <VChart v-else class="mt-4 h-[420px] w-full" :option="options" autoresize />
    <MainlineStateStrip :overview="overview" />
  </section>
</template>
```

- [ ] **Step 4: Wire mainline panel into the page**

Replace `snap-ui/app/pages/index.vue` with:

```vue
<script setup lang="ts">
const dashboard = useSnapshotDashboard()
</script>

<template>
  <main class="min-h-screen px-4 py-4 text-clean-900 sm:px-6 lg:px-8">
    <section class="mx-auto flex max-w-[1680px] flex-col gap-4">
      <MainlineFundingPanel
        :rows="(dashboard.mainlineSeries.data.value as any)?.rows || []"
        :overview="(dashboard.overview.data.value as any) || null"
        :loading="dashboard.mainlineSeries.pending.value"
      />
    </section>
  </main>
</template>
```

- [ ] **Step 5: Verify build**

Run:

```bash
cd snap-ui
npm run build
```

Expected:

```text
✓ built
```

- [ ] **Step 6: Commit mainline UI**

Run:

```bash
git -C snap-ui add app/components app/pages/index.vue
git -C snap-ui commit -m "feat: render mainline funding panel"
```

Expected:

```text
[main ...] feat: render mainline funding panel
```

## Task 11: Build Toolbar And Observation Pool Workspace

**Files:**
- Create: `snap-ui/app/components/SnapshotToolbar.vue`
- Create: `snap-ui/app/components/PoolGroupList.vue`
- Create: `snap-ui/app/components/StockKlineVolumeChart.vue`
- Create: `snap-ui/app/components/ObservationPoolWorkspace.vue`
- Modify: `snap-ui/app/pages/index.vue`

- [ ] **Step 1: Create toolbar**

Create `snap-ui/app/components/SnapshotToolbar.vue`:

```vue
<script setup lang="ts">
const selectedDate = defineModel<string>('selectedDate', { required: true })
const mode = defineModel<'frozen' | 'replay'>('mode', { required: true })
const range = defineModel<'5d' | '10d' | 'all'>('range', { required: true })
const poolFilter = defineModel<string>('poolFilter', { required: true })

defineProps<{
  dates: string[]
}>()

const modeItems = [
  { label: '官方快照', value: 'frozen' },
  { label: 'Replay', value: 'replay' }
]
const rangeItems = [
  { label: '近 5 日', value: '5d' },
  { label: '近 10 日', value: '10d' },
  { label: '全部', value: 'all' }
]
const poolItems = ['全部', '主线核心', '主线备选', '跨线观察', '普通观察'].map((value) => ({ label: value, value }))
</script>

<template>
  <header class="sticky top-0 z-20 rounded-dashboard border border-clean-200 bg-white/95 p-3 shadow-sm backdrop-blur">
    <div class="grid gap-2 md:grid-cols-[1.2fr_1fr_1fr_1fr_auto]">
      <USelect v-model="selectedDate" :items="dates.map((value) => ({ label: value, value }))" icon="i-lucide-calendar-days" />
      <USelect v-model="mode" :items="modeItems" />
      <USelect v-model="range" :items="rangeItems" />
      <USelect v-model="poolFilter" :items="poolItems" icon="i-lucide-list-filter" />
      <UButton color="primary" variant="soft" icon="i-lucide-refresh-cw" @click="$emit('refresh')">
        刷新
      </UButton>
    </div>
  </header>
</template>
```

- [ ] **Step 2: Create pool group list**

Create `snap-ui/app/components/PoolGroupList.vue`:

```vue
<script setup lang="ts">
import type { ObservationPoolGroup } from '../types/snapshot'

const props = defineProps<{
  groups: ObservationPoolGroup[]
  selectedCode: string
  filter: string
}>()
const emit = defineEmits<{ select: [code: string] }>()

const visibleGroups = computed(() => {
  if (props.filter === '全部') return props.groups
  return props.groups
    .map((group) => ({ ...group, rows: group.rows.filter((row) => row.sourcePool === props.filter) }))
    .filter((group) => group.rows.length)
})
</script>

<template>
  <div class="flex max-h-[520px] flex-col gap-3 overflow-auto pr-1">
    <section v-for="group in visibleGroups" :key="group.label" class="rounded-dashboard border border-clean-200 bg-white">
      <div class="border-b border-clean-100 px-3 py-2">
        <p class="text-sm font-semibold text-clean-900">{{ group.label }}</p>
      </div>
      <button
        v-for="row in group.rows"
        :key="row.stockCode"
        class="flex w-full items-center justify-between border-b border-clean-100 px-3 py-2 text-left last:border-b-0 active:scale-[0.99]"
        :class="row.stockCode === selectedCode ? 'bg-wechat-50 text-wechat-800' : 'bg-white text-clean-900 hover:bg-clean-50'"
        @click="emit('select', row.stockCode)"
      >
        <span>
          <span class="block text-sm font-medium">{{ row.stockName }}</span>
          <span class="text-xs text-clean-500">{{ row.stockCode }} · {{ row.currentAction }}</span>
        </span>
        <span class="h-2 w-2 rounded-full" :class="row.poolGroup === 'main' ? 'bg-wechat-500' : 'bg-clean-300'" />
      </button>
    </section>
  </div>
</template>
```

- [ ] **Step 3: Create K-line chart component**

Create `snap-ui/app/components/StockKlineVolumeChart.vue`:

```vue
<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, CandlestickChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import type { StockKlineResponse } from '../types/snapshot'
import { buildKlineOptions } from '../utils/charts/klineOptions'

use([CanvasRenderer, CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent])

const props = defineProps<{
  kline?: StockKlineResponse | null
  loading?: boolean
}>()

const options = computed(() => buildKlineOptions(props.kline?.rows || []))
</script>

<template>
  <section class="rounded-dashboard border border-clean-200 bg-white p-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-xs text-clean-500">观察池标的</p>
        <h3 class="text-lg font-semibold text-clean-900">
          {{ kline?.stockName || kline?.stockCode || '未选择' }}
        </h3>
      </div>
      <DataStatusBadge :status="kline?.status.status" :message="kline?.status.message" />
    </div>
    <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-clean-600 sm:grid-cols-4">
      <p>观察锚点：-</p>
      <p>容忍带：-</p>
      <p>失真线：-</p>
      <p>当前处理：{{ kline?.status.message || '-' }}</p>
    </div>
    <USkeleton v-if="loading" class="mt-4 h-[420px] w-full" />
    <div v-else-if="!kline?.rows?.length" class="mt-4 flex h-[420px] items-center justify-center rounded-dashboard bg-clean-50 text-sm text-clean-500">
      暂无 K 线数据
    </div>
    <VChart v-else class="mt-4 h-[420px] w-full" :option="options" autoresize />
  </section>
</template>
```

- [ ] **Step 4: Create observation workspace**

Create `snap-ui/app/components/ObservationPoolWorkspace.vue`:

```vue
<script setup lang="ts">
import type { ObservationPoolResponse, StockKlineResponse } from '../types/snapshot'

defineProps<{
  pool?: ObservationPoolResponse | null
  kline?: StockKlineResponse | null
  selectedCode: string
  filter: string
  loading?: boolean
}>()

const emit = defineEmits<{ select: [code: string] }>()
</script>

<template>
  <section class="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
    <div class="rounded-dashboard border border-clean-200 bg-clean-50 p-3">
      <div class="mb-3 flex items-center justify-between">
        <div>
          <p class="text-xs font-medium text-wechat-700">观察池</p>
          <h2 class="text-lg font-semibold text-clean-900">候选分组</h2>
        </div>
        <DataStatusBadge :status="pool?.status.status" :message="pool?.status.message" />
      </div>
      <USkeleton v-if="loading" class="h-[420px] w-full" />
      <PoolGroupList v-else :groups="pool?.groups || []" :selected-code="selectedCode" :filter="filter" @select="emit('select', $event)" />
    </div>
    <StockKlineVolumeChart :kline="kline" :loading="loading" />
  </section>
</template>
```

- [ ] **Step 5: Wire toolbar and observation workspace into page**

Replace `snap-ui/app/pages/index.vue` with:

```vue
<script setup lang="ts">
const dashboard = useSnapshotDashboard()

function refreshAll() {
  dashboard.snapshots.refresh()
  dashboard.mainlineSeries.refresh()
  dashboard.overview.refresh()
  dashboard.pool.refresh()
  dashboard.kline.refresh()
}
</script>

<template>
  <main class="min-h-screen px-4 py-4 text-clean-900 sm:px-6 lg:px-8">
    <section class="mx-auto flex max-w-[1680px] flex-col gap-4">
      <SnapshotToolbar
        v-model:selected-date="dashboard.selectedDate.value"
        v-model:mode="dashboard.mode.value"
        v-model:range="dashboard.range.value"
        v-model:pool-filter="dashboard.poolFilter.value"
        :dates="dashboard.snapshots.data.value?.dates || []"
        @refresh="refreshAll"
      />
      <MainlineFundingPanel
        :rows="(dashboard.mainlineSeries.data.value as any)?.rows || []"
        :overview="(dashboard.overview.data.value as any) || null"
        :loading="dashboard.mainlineSeries.pending.value"
      />
      <ObservationPoolWorkspace
        :pool="(dashboard.pool.data.value as any) || null"
        :kline="(dashboard.kline.data.value as any) || null"
        :selected-code="dashboard.selectedStockCode.value"
        :filter="dashboard.poolFilter.value"
        :loading="dashboard.pool.pending.value"
        @select="dashboard.selectedStockCode.value = $event"
      />
    </section>
  </main>
</template>
```

- [ ] **Step 6: Verify build**

Run:

```bash
cd snap-ui
npm run build
```

Expected:

```text
✓ built
```

- [ ] **Step 7: Commit observation UI**

Run:

```bash
git -C snap-ui add app/components app/pages/index.vue
git -C snap-ui commit -m "feat: render observation pool workspace"
```

Expected:

```text
[main ...] feat: render observation pool workspace
```

## Task 12: Final Verification And Visual QA

**Files:**
- Create: `snap-ui/tests/e2e/dashboard.spec.ts`
- Modify: `snap-ui/package.json`
- Verify: `snap-ui/` independent git status
- Verify: parent git status does not include `snap-ui/`

- [ ] **Step 1: Install Playwright browser runtime**

Run:

```bash
cd snap-ui
npx playwright install chromium
```

Expected:

```text
chromium
```

- [ ] **Step 2: Add Playwright smoke test**

Create `snap-ui/tests/e2e/dashboard.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

test('dashboard renders mainline and observation sections', async ({ page }) => {
  await page.goto('http://127.0.0.1:3040/')
  await expect(page.getByText('主线成交额占比')).toBeVisible()
  await expect(page.getByText('观察池')).toBeVisible()
})
```

- [ ] **Step 3: Run unit tests**

Run:

```bash
cd snap-ui
npm run test
```

Expected:

```text
PASS
```

- [ ] **Step 4: Run production build**

Run:

```bash
cd snap-ui
npm run build
```

Expected:

```text
✓ built
```

- [ ] **Step 5: Run local dev server**

Run:

```bash
cd snap-ui
npm run dev
```

Expected:

```text
Local: http://127.0.0.1:3040/
```

- [ ] **Step 6: Run E2E smoke test while dev server is running**

Run in another terminal:

```bash
cd snap-ui
npm run test:e2e
```

Expected:

```text
1 passed
```

- [ ] **Step 7: Manually verify visual acceptance in browser**

Open:

```text
http://127.0.0.1:3040/
```

Verify:

- Toolbar is white, compact, and wraps without text overflow.
- Mainline chart is the first dominant panel.
- All mainline line series render as smooth curves.
- Observation pool rows appear below the mainline panel.
- Selecting a stock updates the right-side K-line panel.
- White / grey / WeChat-green theme is consistent.
- Missing K-line data shows `暂无 K 线数据`, not fake zeroes.

- [ ] **Step 8: Commit verification assets**

Run:

```bash
git -C snap-ui add tests/e2e/dashboard.spec.ts package.json package-lock.json
git -C snap-ui commit -m "test: add dashboard smoke coverage"
```

Expected:

```text
[main ...] test: add dashboard smoke coverage
```

- [ ] **Step 9: Verify parent repository remains isolated**

Run from the parent repository:

```bash
git status --short
git status --ignored --short snap-ui | head
```

Expected:

```text
# parent status does not list snap-ui as tracked or untracked source
!! snap-ui/
```

## Self-Review

Spec coverage:

- Nuxt 4, Nuxt UI, Reka as fallback, and ECharts are covered by Tasks 1, 2, 8, 10, and 11.
- `snap-ui/` independent repository placement is covered by Tasks 1 and 12.
- White / grey / WeChat-green theme is covered by Task 2.
- Mainline smooth-line chart is covered by Tasks 4, 8, and 10.
- Observation pool grouping and selected-stock K-line/volume chart are covered by Tasks 5, 6, 8, and 11.
- Server API data layer is covered by Tasks 3, 4, 5, 6, and 7.
- Empty data and no fake zeroes are covered by Tasks 5, 6, and 11.
- Testing and visual verification are covered by Tasks 3 through 12.

Placeholder scan:

- The plan contains concrete files, commands, code snippets, and expected outputs.
- The plan avoids unspecified implementation steps and does not rely on untracked parent-repository changes.

Type consistency:

- Shared API types are introduced in `app/types/snapshot.ts` and reused by adapters, chart builders, and Vue components.
- Server utilities consistently return `SourceStatus`, `DataStatus`, `MainlineOverview`, `ObservationPoolResponse`, and `StockKlineResponse`.
- Chart builders accept the same row types returned by server adapters.
