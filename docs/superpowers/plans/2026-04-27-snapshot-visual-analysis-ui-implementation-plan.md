# Snapshot Zhongshu Visual Analysis UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. If subagents are spawned from this checkout, set `model` to `gpt-5.5` and `reasoning_effort` to `xhigh`.

**Goal:** Re-center the independent `snap-ui/` Nuxt app around a first-screen `日线中枢结构` K-line chart with zhongshu rectangles, ZG/ZD labels, and big/small mainline annotations.

**Architecture:** Continue from the existing `snap-ui/` app and its scanner/path-safety baseline. Nuxt server utilities normalize parent-repo snapshot data into typed JSON contracts; ECharts renders candlestick, volume, zhongshu zone overlays, smooth mainline turnover lines, and selected observation-pool K-line charts. If snapshots do not contain index K-line rows, add a parent-repo Python export helper that reuses `scripts/decision/zhongshu_runtime.py` instead of fabricating rows.

**Tech Stack:** Nuxt 4, Vue 3, Nuxt UI, Tailwind CSS v4 theme tokens, ECharts, vue-echarts, TypeScript, Vitest, Happy DOM, Playwright.

---

## Current Baseline

Already completed in the independent `snap-ui/` repository:

- Nuxt app scaffolded in `snap-ui/`.
- Nuxt UI, ECharts, vue-echarts, zod, Vitest, Playwright installed.
- White / grey / WeChat-green theme baseline exists.
- Snapshot scanner exists at `snap-ui/server/utils/snapshot/scanner.ts`.
- Parent path resolver exists at `snap-ui/server/utils/sourcePath.ts`.
- Unit tests exist for scanner and path safety.

This plan does not redo those tasks.

## File Structure

Parent repository files:

- Modify: `docs/superpowers/plans/2026-04-27-snapshot-visual-analysis-ui-implementation-plan.md`
- Reference: `docs/superpowers/specs/2026-04-27-snapshot-visual-analysis-ui-design.md`
- Optional create: `scripts/export/zhongshu_visual_snapshot.py`
- Optional test: `tests/test_zhongshu_visual_snapshot_export.py`

Independent UI project files under `snap-ui/`:

- Modify: `app/types/snapshot.ts`
- Modify: `app/pages/index.vue`
- Create: `app/composables/useZhongshuDashboard.ts`
- Create: `app/components/SnapshotToolbar.vue`
- Create: `app/components/ZhongshuStructurePanel.vue`
- Create: `app/components/ZhongshuKlineChart.vue`
- Create: `app/components/ZhongshuDetailStrip.vue`
- Create: `app/components/ZhongshuZoneLegend.vue`
- Create: `app/components/ZhongshuMainlineBadge.vue`
- Create: `app/components/DataStatusBadge.vue`
- Create: `app/components/MainlineFundingPanel.vue`
- Create: `app/components/ObservationPoolWorkspace.vue`
- Create: `app/utils/charts/zhongshuOptions.ts`
- Create: `app/utils/charts/mainlineOptions.ts`
- Create: `app/utils/charts/stockKlineOptions.ts`
- Create: `server/api/zhongshu-structure.get.ts`
- Create: `server/api/mainline-series.get.ts`
- Create: `server/api/observation-pool.get.ts`
- Create: `server/api/observation-pool/[code]/kline.get.ts`
- Create: `server/utils/snapshot/loadSnapshot.ts`
- Create: `server/utils/snapshot/zhongshuAdapter.ts`
- Create: `server/utils/snapshot/mainlineMapper.ts`
- Create: `server/utils/snapshot/mainlineSeriesAdapter.ts`
- Create: `server/utils/snapshot/observationPoolAdapter.ts`
- Create: `server/utils/snapshot/stockKlineAdapter.ts`
- Test: `tests/unit/zhongshuAdapter.test.ts`
- Test: `tests/unit/mainlineMapper.test.ts`
- Test: `tests/unit/zhongshuOptions.test.ts`
- Test: `tests/unit/mainlineOptions.test.ts`
- Test: `tests/unit/observationPoolAdapter.test.ts`
- Test: `tests/e2e/dashboard.spec.ts`

## Task 1: Define Zhongshu Contracts And Adapter

**Files:**
- Modify: `snap-ui/app/types/snapshot.ts`
- Create: `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`
- Create: `snap-ui/tests/unit/zhongshuAdapter.test.ts`

- [ ] **Step 1: Add failing adapter tests**

Create `snap-ui/tests/unit/zhongshuAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { normalizeZhongshuStructure } from '../../server/utils/snapshot/zhongshuAdapter'

const klineRows = [
  { date: '2026-04-20', open: 3000, close: 3012, low: 2988, high: 3020, volume: 100, amount: 1000 },
  { date: '2026-04-21', open: 3012, close: 3024, low: 3008, high: 3030, volume: 110, amount: 1100 },
  { date: '2026-04-22', open: 3024, close: 3018, low: 3000, high: 3032, volume: 105, amount: 1050 },
  { date: '2026-04-23', open: 3018, close: 3036, low: 3010, high: 3044, volume: 120, amount: 1200 },
  { date: '2026-04-24', open: 3036, close: 3042, low: 3026, high: 3050, volume: 130, amount: 1300 }
]

describe('normalizeZhongshuStructure', () => {
  it('normalizes current zhongshu zone with big and small mainline labels', () => {
    const snapshot = {
      data: {
        index_klines: { sh000001: klineRows },
        market_zhongshu: {
          success: true,
          today_date: '2026-04-24',
          today_price: 3042,
          current_zhongshu: {
            start_date: '2026-04-20',
            end_date: '2026-04-24',
            zg: 3050,
            zd: 2988,
            kline_count: 5,
            segment_type: 'zhongshu'
          },
          zhongshu_list: [
            {
              start_date: '2026-04-20',
              end_date: '2026-04-24',
              zg: 3050,
              zd: 2988,
              kline_count: 5,
              segment_type: 'zhongshu'
            }
          ],
          structure_segments: [],
          latest_structure_segment: { segment_type: 'zhongshu' },
          signal: {
            status: '中枢内',
            signal_type: '观察',
            comparison_state: '中枢内震荡',
            zg: 3050,
            zd: 2988,
            dist_to_zg: -0.0026,
            dist_to_zd: 0.0181
          }
        },
        appendix_b: {
          structure_mainline_records: [
            {
              date_range: '2026-04-20~2026-04-24',
              pivot_level: '日线中枢',
              mainline: '机器人',
              mainline_degree: '大主线'
            },
            {
              date_range: '2026-04-24',
              pivot_level: '60分钟',
              mainline: '低空经济',
              mainline_degree: '小主线'
            }
          ]
        }
      }
    }

    const result = normalizeZhongshuStructure(snapshot, {
      date: '2026-04-24',
      mode: 'frozen',
      indexCode: 'sh000001'
    })

    expect(result.status.status).toBe('success')
    expect(result.rows).toHaveLength(5)
    expect(result.zones[0]).toMatchObject({
      startDate: '2026-04-20',
      endDate: '2026-04-24',
      zg: 3050,
      zd: 2988,
      isCurrent: true,
      bigMainline: '机器人',
      smallMainline: '低空经济',
      structureState: '中枢内'
    })
  })

  it('does not fabricate rows when index kline data is missing', () => {
    const result = normalizeZhongshuStructure(
      { data: { market_zhongshu: { success: true, zhongshu_list: [] } } },
      { date: '2026-04-24', mode: 'frozen', indexCode: 'sh000001' }
    )

    expect(result.rows).toEqual([])
    expect(result.status).toMatchObject({
      status: 'missing',
      sourceField: 'index_klines.sh000001'
    })
  })

  it('rejects zhongshu ranges without zg or zd', () => {
    const result = normalizeZhongshuStructure(
      {
        data: {
          index_klines: { sh000001: klineRows },
          market_zhongshu: {
            success: true,
            zhongshu_list: [{ start_date: '2026-04-20', end_date: '2026-04-24', zg: 3050 }]
          }
        }
      },
      { date: '2026-04-24', mode: 'frozen', indexCode: 'sh000001' }
    )

    expect(result.zones).toEqual([])
    expect(result.status.status).toBe('degraded')
    expect(result.status.sourceField).toBe('market_zhongshu.zhongshu_list[].zd')
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/zhongshuAdapter.test.ts
```

Expected: FAIL because `zhongshuAdapter.ts` does not exist.

- [ ] **Step 3: Extend shared types**

Append these contracts to `snap-ui/app/types/snapshot.ts`:

```ts
export type IndexCode = 'sh000001' | 'sz399001' | 'sz399006' | string

export interface ZhongshuKlineRow extends KlineRow {
  amount: number | null
}

export interface ZhongshuZone {
  id: string
  startDate: string
  endDate: string
  zg: number
  zd: number
  klineCount: number
  segmentType: 'zhongshu' | 'connector'
  connectorRole: 'leading' | 'between' | 'trailing' | ''
  isCurrent: boolean
  isLatest: boolean
  structureState: string
  bigMainline: string
  smallMainline: string
  mainlineDegree: string
  evolution: string
  replacement: string
  interpretation: string
  sourceStatus: SourceStatus
}

export interface ZhongshuSignal {
  status: string
  signalType: string
  comparisonState: string
  zg: number | null
  zd: number | null
  distToZg: number | null
  distToZd: number | null
}

export interface ZhongshuStructureResponse {
  date: string
  mode: SnapshotMode
  indexCode: IndexCode
  indexName: string
  rows: ZhongshuKlineRow[]
  zones: ZhongshuZone[]
  selectedZoneId: string
  todayDate: string
  todayPrice: number | null
  signal: ZhongshuSignal
  status: DataStatus
}
```

- [ ] **Step 4: Implement the normalizer**

Create `snap-ui/server/utils/snapshot/zhongshuAdapter.ts`:

```ts
import type {
  DataStatus,
  IndexCode,
  SnapshotMode,
  ZhongshuKlineRow,
  ZhongshuSignal,
  ZhongshuStructureResponse,
  ZhongshuZone
} from '../../../app/types/snapshot'

interface NormalizeOptions {
  date: string
  mode: SnapshotMode
  indexCode: IndexCode
}

const INDEX_NAME_BY_CODE: Record<string, string> = {
  sh000001: '上证指数',
  sz399001: '深证成指',
  sz399006: '创业板指'
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord).filter((item) => Object.keys(item).length > 0) : []
}

function asNumber(value: unknown): number | null {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function asText(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function rootOf(snapshot: unknown): Record<string, unknown> {
  const root = asRecord(snapshot)
  return asRecord(root.data || root)
}

function normalizeRows(root: Record<string, unknown>, indexCode: string): ZhongshuKlineRow[] {
  const indexKlines = asRecord(root.index_klines || root.indexKlines)
  const rows = asArray(indexKlines[indexCode] || root.index_kline_rows || root.indexKlineRows)

  return rows
    .map((row) => ({
      date: asText(row.date),
      open: asNumber(row.open),
      close: asNumber(row.close),
      low: asNumber(row.low),
      high: asNumber(row.high),
      volume: asNumber(row.volume),
      amount: asNumber(row.amount),
      dailyChangePct: asNumber(row.dailyChangePct ?? row.daily_change_pct),
      cumulativeChangePct: asNumber(row.cumulativeChangePct ?? row.cumulative_change_pct)
    }))
    .filter((row): row is ZhongshuKlineRow => {
      return Boolean(row.date) && row.open !== null && row.close !== null && row.low !== null && row.high !== null
    })
}

function collectMainlineRows(root: Record<string, unknown>): Record<string, unknown>[] {
  const marketResearch = asRecord(root.market_research_snapshot)
  const appendixB = asRecord(root.appendix_b)
  return [
    ...asArray(marketResearch.pivot_mainline_rows),
    ...asArray(marketResearch.pivot_mainline_history),
    ...asArray(appendixB.structure_mainline_records),
    ...asArray(root.pivot_mainline_rows),
    ...asArray(root.pivot_mainline_history)
  ]
}

function resolveMainlines(root: Record<string, unknown>) {
  const rows = collectMainlineRows(root)
  const currentRecord = asRecord(root.current_mainline_history_record)
  const summary = asRecord(asRecord(root.mainline_turnover_summary).double_mainline_summary || root.double_mainline_summary)

  const big = rows.find((row) => asText(row.mainline_degree).includes('大主线'))
  const small = rows.find((row) => asText(row.mainline_degree).includes('小主线'))

  return {
    bigMainline: asText(big?.mainline || currentRecord.primary_mainline || currentRecord.leading_line, '待确认'),
    smallMainline: asText(small?.mainline || summary.daily_attack_line, '待确认'),
    bigRow: big,
    smallRow: small
  }
}

function normalizeSignal(signal: Record<string, unknown>): ZhongshuSignal {
  return {
    status: asText(signal.status, '待确认'),
    signalType: asText(signal.signal_type || signal.signalType, '待确认'),
    comparisonState: asText(signal.comparison_state || signal.comparisonState, '待确认'),
    zg: asNumber(signal.zg),
    zd: asNumber(signal.zd),
    distToZg: asNumber(signal.dist_to_zg || signal.distToZg),
    distToZd: asNumber(signal.dist_to_zd || signal.distToZd)
  }
}

function status(status: DataStatus['status'], message: string, sourceField?: string): DataStatus {
  return { status, message, sourceField }
}

export function normalizeZhongshuStructure(snapshot: unknown, options: NormalizeOptions): ZhongshuStructureResponse {
  const root = rootOf(snapshot)
  const marketZhongshu = asRecord(root.market_zhongshu)
  const rows = normalizeRows(root, String(options.indexCode))
  const signal = normalizeSignal(asRecord(marketZhongshu.signal))
  const current = asRecord(marketZhongshu.current_zhongshu)
  const latest = asRecord(marketZhongshu.latest_structure_segment)
  const mainlines = resolveMainlines(root)
  const sourceZones = asArray(marketZhongshu.zhongshu_list)

  let responseStatus = status('success', '已读取中枢结构', 'market_zhongshu')
  if (!marketZhongshu.success && sourceZones.length === 0) {
    responseStatus = status('missing', '快照缺少 market_zhongshu', 'market_zhongshu')
  }
  if (rows.length === 0) {
    responseStatus = status('missing', '暂无中枢 K 线数据', `index_klines.${options.indexCode}`)
  }

  const zones: ZhongshuZone[] = []
  for (const [index, zone] of sourceZones.entries()) {
    const zg = asNumber(zone.zg)
    const zd = asNumber(zone.zd)
    if (zg === null || zd === null) {
      responseStatus = status('degraded', '中枢区间缺少 ZG/ZD', zg === null ? 'market_zhongshu.zhongshu_list[].zg' : 'market_zhongshu.zhongshu_list[].zd')
      continue
    }
    const startDate = asText(zone.start_date || zone.startDate)
    const endDate = asText(zone.end_date || zone.endDate)
    const isCurrent = startDate === asText(current.start_date || current.startDate) && endDate === asText(current.end_date || current.endDate)
    zones.push({
      id: `zhongshu-${index + 1}-${startDate}-${endDate}`,
      startDate,
      endDate,
      zg,
      zd,
      klineCount: asNumber(zone.kline_count || zone.klineCount) ?? 0,
      segmentType: asText(zone.segment_type || zone.segmentType, 'zhongshu') === 'connector' ? 'connector' : 'zhongshu',
      connectorRole: asText(zone.connector_role || zone.connectorRole) as ZhongshuZone['connectorRole'],
      isCurrent,
      isLatest: index === sourceZones.length - 1 || (startDate === asText(latest.start_date) && endDate === asText(latest.end_date)),
      structureState: signal.status,
      bigMainline: mainlines.bigMainline,
      smallMainline: mainlines.smallMainline,
      mainlineDegree: asText(mainlines.bigRow?.mainline_degree || mainlines.smallRow?.mainline_degree, '待确认'),
      evolution: asText(mainlines.bigRow?.evolution || mainlines.smallRow?.evolution, '待确认'),
      replacement: asText(mainlines.bigRow?.replacement || mainlines.smallRow?.replacement, '待确认'),
      interpretation: asText(mainlines.bigRow?.interpretation || mainlines.smallRow?.interpretation, ''),
      sourceStatus: mainlines.bigMainline === '待确认' && mainlines.smallMainline === '待确认' ? 'missing' : 'success'
    })
  }

  return {
    date: options.date,
    mode: options.mode,
    indexCode: options.indexCode,
    indexName: INDEX_NAME_BY_CODE[String(options.indexCode)] || String(options.indexCode),
    rows,
    zones,
    selectedZoneId: zones.find((zone) => zone.isCurrent)?.id || zones.at(-1)?.id || '',
    todayDate: asText(marketZhongshu.today_date || options.date),
    todayPrice: asNumber(marketZhongshu.today_price),
    signal,
    status: responseStatus
  }
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/zhongshuAdapter.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit in `snap-ui`**

Run:

```bash
git -C snap-ui add app/types/snapshot.ts server/utils/snapshot/zhongshuAdapter.ts tests/unit/zhongshuAdapter.test.ts
git -C snap-ui commit -m "feat: normalize zhongshu structure data"
```

Expected: commit succeeds in the independent UI repository.

## Task 2: Add Snapshot Loading And Zhongshu API

**Files:**
- Create: `snap-ui/server/utils/snapshot/loadSnapshot.ts`
- Create: `snap-ui/server/api/zhongshu-structure.get.ts`
- Test: `snap-ui/tests/unit/loadSnapshot.test.ts`

- [ ] **Step 1: Add loader tests**

Create `snap-ui/tests/unit/loadSnapshot.test.ts`:

```ts
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { afterEach, describe, expect, it } from 'vitest'
import { loadSnapshotForDate } from '../../server/utils/snapshot/loadSnapshot'

const roots: string[] = []

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), 'snap-ui-load-'))
  roots.push(root)
  await mkdir(join(root, 'snapshots', 'replay'), { recursive: true })
  return root
}

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

describe('loadSnapshotForDate', () => {
  it('loads frozen snapshots by date', async () => {
    const root = await makeRoot()
    await writeFile(join(root, 'snapshots', '2026-04-27.json'), '{"data":{"ok":true}}')

    await expect(loadSnapshotForDate(root, '2026-04-27', 'frozen')).resolves.toEqual({ data: { ok: true } })
  })

  it('loads replay snapshots by date', async () => {
    const root = await makeRoot()
    await writeFile(join(root, 'snapshots', 'replay', '2026-04-24_replay.json'), '{"data":{"mode":"replay"}}')

    await expect(loadSnapshotForDate(root, '2026-04-24', 'replay')).resolves.toEqual({ data: { mode: 'replay' } })
  })

  it('rejects invalid date strings before touching the filesystem', async () => {
    const root = await makeRoot()
    await expect(loadSnapshotForDate(root, '../bad', 'frozen')).rejects.toThrow('Invalid snapshot date')
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/loadSnapshot.test.ts
```

Expected: FAIL because the loader does not exist.

- [ ] **Step 3: Implement snapshot loader**

Create `snap-ui/server/utils/snapshot/loadSnapshot.ts`:

```ts
import { readFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'
import type { SnapshotMode } from '../../../app/types/snapshot'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export function snapshotPathForDate(root: string, date: string, mode: SnapshotMode) {
  if (!DATE_RE.test(date)) {
    throw new Error(`Invalid snapshot date: ${date}`)
  }
  const base = resolve(root)
  const filePath = mode === 'replay'
    ? resolve(join(base, 'snapshots', 'replay', `${date}_replay.json`))
    : resolve(join(base, 'snapshots', `${date}.json`))
  if (!filePath.startsWith(`${base}/`)) {
    throw new Error(`Snapshot path escaped root: ${filePath}`)
  }
  return filePath
}

export async function loadSnapshotForDate(root: string, date: string, mode: SnapshotMode) {
  const filePath = snapshotPathForDate(root, date, mode)
  const raw = await readFile(filePath, 'utf8')
  return JSON.parse(raw) as unknown
}
```

- [ ] **Step 4: Implement API endpoint**

Create `snap-ui/server/api/zhongshu-structure.get.ts`:

```ts
import { getQuery } from 'h3'
import type { SnapshotMode } from '../../app/types/snapshot'
import { resolveDailyReportRoot } from '../utils/sourcePath'
import { loadSnapshotForDate } from '../utils/snapshot/loadSnapshot'
import { normalizeZhongshuStructure } from '../utils/snapshot/zhongshuAdapter'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const INDEX_RE = /^(sh|sz)\d{6}$/

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const date = String(query.date || '')
  const mode = String(query.mode || 'frozen') as SnapshotMode
  const indexCode = String(query.index || 'sh000001')

  if (!DATE_RE.test(date)) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid date' })
  }
  if (mode !== 'frozen' && mode !== 'replay') {
    throw createError({ statusCode: 400, statusMessage: 'Invalid mode' })
  }
  if (!INDEX_RE.test(indexCode)) {
    throw createError({ statusCode: 400, statusMessage: 'Invalid index' })
  }

  const root = resolveDailyReportRoot()
  const snapshot = await loadSnapshotForDate(root, date, mode)
  return normalizeZhongshuStructure(snapshot, { date, mode, indexCode })
})
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/loadSnapshot.test.ts tests/unit/sourcePath.test.ts
```

Expected: PASS.

- [ ] **Step 6: Type-check**

Run:

```bash
cd snap-ui
npx vue-tsc --noEmit
```

Expected: PASS.

- [ ] **Step 7: Commit in `snap-ui`**

Run:

```bash
git -C snap-ui add server/utils/snapshot/loadSnapshot.ts server/api/zhongshu-structure.get.ts tests/unit/loadSnapshot.test.ts
git -C snap-ui commit -m "feat: expose zhongshu structure api"
```

Expected: commit succeeds.

## Task 3: Add Parent Export Helper If K-Line Rows Are Absent

**Files:**
- Create if needed: `scripts/export/__init__.py`
- Create if needed: `scripts/export/zhongshu_visual_snapshot.py`
- Create if needed: `tests/test_zhongshu_visual_snapshot_export.py`

- [ ] **Step 1: Inspect current snapshots for index K-line rows**

Run from the parent repository:

```bash
python - <<'PY'
import json
from pathlib import Path

for path in sorted(Path('snapshots').glob('*.json'))[-3:]:
    data = json.loads(path.read_text())
    root = data.get('data', data)
    has_rows = bool(root.get('index_klines') or root.get('index_kline_rows') or root.get('market_zhongshu', {}).get('kline_rows'))
    print(path, has_rows)
PY
```

Expected: print whether the newest snapshots already contain usable index K-line rows.

- [ ] **Step 2: If rows exist, skip this task and record why**

Run:

```bash
git status --short scripts/export tests/test_zhongshu_visual_snapshot_export.py
```

Expected: no new files for this task.

- [ ] **Step 3: If rows do not exist, write failing export-helper tests**

Create `tests/test_zhongshu_visual_snapshot_export.py`:

```python
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export.zhongshu_visual_snapshot import normalize_visual_payload


def test_normalize_visual_payload_keeps_kline_rows_and_zones():
    payload = normalize_visual_payload(
        {
            "success": True,
            "today_date": "2026-04-24",
            "today_price": 3042,
            "zhongshu_list": [
                {
                    "start_date": "2026-04-20",
                    "end_date": "2026-04-24",
                    "zg": 3050,
                    "zd": 2988,
                    "kline_count": 5,
                    "segment_type": "zhongshu",
                }
            ],
            "signal": {"status": "中枢内"},
        },
        [
            {"date": "2026-04-24", "open": 3036, "high": 3050, "low": 3026, "close": 3042, "volume": 130, "amount": 1300}
        ],
        date="2026-04-24",
        index_code="sh000001",
    )

    assert payload["date"] == "2026-04-24"
    assert payload["index_code"] == "sh000001"
    assert payload["market_zhongshu"]["zhongshu_list"][0]["zg"] == 3050
    assert payload["index_klines"]["sh000001"][0]["close"] == 3042


def test_cli_writes_json_with_injected_runner(tmp_path, monkeypatch):
    from export import zhongshu_visual_snapshot as module

    def fake_runner(target_date, index_code):
        return (
            {"success": True, "today_date": target_date, "today_price": 1, "zhongshu_list": [], "signal": {}},
            [{"date": target_date, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1}],
        )

    out = tmp_path / "visual.json"
    module.main(["--date", "2026-04-24", "--index-code", "sh000001", "--output", str(out)], runner=fake_runner)

    written = json.loads(out.read_text())
    assert written["date"] == "2026-04-24"
    assert written["index_klines"]["sh000001"][0]["date"] == "2026-04-24"
```

- [ ] **Step 4: Run tests to verify failure**

Run:

```bash
pytest tests/test_zhongshu_visual_snapshot_export.py -q
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 5: Implement export helper**

Create `scripts/export/__init__.py`:

```python
"""Export helpers for visual UI data contracts."""
```

Create `scripts/export/zhongshu_visual_snapshot.py`:

```python
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable

from decision.zhongshu_runtime import analyze_market_zhongshu, split_zhongshu_history_and_today
from market_data.daily_price_runtime import fetch_daily_price_bars


def _index_to_bs_code(index_code: str) -> str:
    text = str(index_code or "sh000001").lower().replace(".", "")
    if text.startswith("sh"):
        return f"sh.{text[2:]}"
    if text.startswith("sz"):
        return f"sz.{text[2:]}"
    return text


def _start_date_for(target_date: str, recent_days: int) -> str:
    parsed = dt.datetime.strptime(target_date, "%Y-%m-%d").date()
    return (parsed - dt.timedelta(days=recent_days * 2)).isoformat()


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": str(row.get("date", ""))[:10],
        "open": float(row.get("open", 0) or 0),
        "high": float(row.get("high", 0) or 0),
        "low": float(row.get("low", 0) or 0),
        "close": float(row.get("close", 0) or 0),
        "volume": float(row.get("volume", 0) or 0),
        "amount": float(row.get("amount", 0) or 0),
    }


def normalize_visual_payload(
    market_zhongshu: dict[str, Any],
    kline_rows: list[dict[str, Any]],
    *,
    date: str,
    index_code: str,
) -> dict[str, Any]:
    return {
        "date": date,
        "index_code": index_code,
        "market_zhongshu": market_zhongshu,
        "index_klines": {index_code: [_normalize_row(row) for row in kline_rows]},
        "source_status": "success" if kline_rows else "missing",
    }


def run_analysis(target_date: str, index_code: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    import pandas as pd

    start_date = _start_date_for(target_date, 120)
    bars = fetch_daily_price_bars(
        _index_to_bs_code(index_code),
        start_date,
        target_date,
        is_index=True,
        prefer_fast=True,
    )
    frame = pd.DataFrame(bars or [])
    result = analyze_market_zhongshu(
        index_code=index_code,
        target_date=target_date,
        fetch_dataframe=lambda **_: frame,
        print_fn=lambda *_args, **_kwargs: None,
    )
    recent_df, _hist_df, _today_df = split_zhongshu_history_and_today(frame, recent_days=120, target_date=target_date)
    rows = recent_df.drop(columns=[col for col in ["_date_obj"] if col in recent_df.columns]).to_dict("records")
    return result, rows


def main(argv: list[str] | None = None, *, runner: Callable[[str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = run_analysis) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--index-code", default="sh000001")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    market_zhongshu, rows = runner(args.date, args.index_code)
    payload = normalize_visual_payload(market_zhongshu, rows, date=args.date, index_code=args.index_code)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run helper tests**

Run:

```bash
pytest tests/test_zhongshu_visual_snapshot_export.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit parent helper only if created**

Run:

```bash
git add scripts/export/__init__.py scripts/export/zhongshu_visual_snapshot.py tests/test_zhongshu_visual_snapshot_export.py
git commit -m "feat: export zhongshu visual snapshot data"
```

Expected: commit succeeds in parent repository. Do not stage unrelated dirty files.

## Task 4: Build Zhongshu ECharts Option Builder

**Files:**
- Create: `snap-ui/app/utils/charts/zhongshuOptions.ts`
- Create: `snap-ui/tests/unit/zhongshuOptions.test.ts`

- [ ] **Step 1: Add failing chart option tests**

Create `snap-ui/tests/unit/zhongshuOptions.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildZhongshuKlineOptions } from '../../app/utils/charts/zhongshuOptions'
import type { ZhongshuKlineRow, ZhongshuZone } from '../../app/types/snapshot'

const rows: ZhongshuKlineRow[] = [
  { date: '2026-04-20', open: 3000, close: 3012, low: 2988, high: 3020, volume: 100, amount: 1000, dailyChangePct: null, cumulativeChangePct: null },
  { date: '2026-04-24', open: 3036, close: 3042, low: 3026, high: 3050, volume: 130, amount: 1300, dailyChangePct: null, cumulativeChangePct: null }
]

const zones: ZhongshuZone[] = [
  {
    id: 'z1',
    startDate: '2026-04-20',
    endDate: '2026-04-24',
    zg: 3050,
    zd: 2988,
    klineCount: 5,
    segmentType: 'zhongshu',
    connectorRole: '',
    isCurrent: true,
    isLatest: true,
    structureState: '中枢内',
    bigMainline: '机器人',
    smallMainline: '低空经济',
    mainlineDegree: '大主线',
    evolution: '震荡',
    replacement: '待确认',
    interpretation: '',
    sourceStatus: 'success'
  }
]

describe('buildZhongshuKlineOptions', () => {
  it('creates candlestick, volume and zhongshu rectangle overlays', () => {
    const option = buildZhongshuKlineOptions(rows, zones, { showZones: true, showLabels: true, selectedZoneId: 'z1' })
    const candleSeries = option.series?.[0] as any
    const volumeSeries = option.series?.[1] as any

    expect(candleSeries.type).toBe('candlestick')
    expect(volumeSeries.type).toBe('bar')
    expect(candleSeries.markArea.data[0]).toEqual([
      expect.objectContaining({ xAxis: '2026-04-20', yAxis: 2988 }),
      expect.objectContaining({ xAxis: '2026-04-24', yAxis: 3050 })
    ])
    expect(candleSeries.markArea.data[0][1].label.formatter).toContain('大主线: 机器人')
    expect(candleSeries.markLine.data).toContainEqual(expect.objectContaining({ yAxis: 3042 }))
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/zhongshuOptions.test.ts
```

Expected: FAIL because the option builder does not exist.

- [ ] **Step 3: Implement chart option builder**

Create `snap-ui/app/utils/charts/zhongshuOptions.ts`:

```ts
import type { ComposeOption } from 'echarts/core'
import type { ZhongshuKlineRow, ZhongshuZone } from '../../types/snapshot'

interface ZhongshuChartOptions {
  showZones: boolean
  showLabels: boolean
  selectedZoneId: string
}

function zoneLabel(zone: ZhongshuZone) {
  return [
    `${zone.startDate} ~ ${zone.endDate}`,
    `ZG: ${zone.zg.toFixed(2)} / ZD: ${zone.zd.toFixed(2)}`,
    `大主线: ${zone.bigMainline || '待确认'}`,
    `小主线: ${zone.smallMainline || '待确认'}`,
    `状态: ${zone.structureState || '待确认'}`
  ].join('\n')
}

export function buildZhongshuKlineOptions(
  rows: ZhongshuKlineRow[],
  zones: ZhongshuZone[],
  options: ZhongshuChartOptions
): ComposeOption<any> {
  const dates = rows.map((row) => row.date)
  const candleData = rows.map((row) => [row.open, row.close, row.low, row.high])
  const volumeData = rows.map((row) => row.volume ?? 0)
  const today = rows.at(-1)

  return {
    animationDuration: 180,
    color: ['#07C160', '#D64545'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 48, right: 24, top: 32, height: '62%' },
      { left: 48, right: 24, top: '76%', height: '14%' }
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#DCE2DE' } } },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: true, axisLabel: { show: false }, axisLine: { lineStyle: { color: '#DCE2DE' } } }
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: '#EEF0EE' } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, splitLine: { show: false } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], height: 18, bottom: 8, borderColor: '#E6E8E6' }
    ],
    series: [
      {
        name: '日线',
        type: 'candlestick',
        data: candleData,
        itemStyle: {
          color: '#D64545',
          color0: '#128C45',
          borderColor: '#D64545',
          borderColor0: '#128C45'
        },
        markArea: {
          silent: false,
          itemStyle: { color: 'rgba(7, 193, 96, 0.08)', borderColor: '#128C45', borderWidth: 1 },
          emphasis: { itemStyle: { color: 'rgba(7, 193, 96, 0.14)' } },
          data: options.showZones
            ? zones.map((zone) => {
                const selected = zone.id === options.selectedZoneId
                return [
                  {
                    name: zone.id,
                    xAxis: zone.startDate,
                    yAxis: zone.zd,
                    itemStyle: {
                      color: selected ? 'rgba(7, 193, 96, 0.12)' : 'rgba(107, 117, 110, 0.05)',
                      borderColor: selected ? '#128C45' : '#C9D1CC',
                      borderWidth: selected ? 1.5 : 1
                    }
                  },
                  {
                    xAxis: zone.endDate,
                    yAxis: zone.zg,
                    label: {
                      show: options.showLabels && selected,
                      position: 'insideTopLeft',
                      color: '#1F2A24',
                      fontSize: 11,
                      lineHeight: 16,
                      formatter: zoneLabel(zone)
                    }
                  }
                ]
              })
            : []
        },
        markLine: today
          ? {
              symbol: 'none',
              lineStyle: { color: '#6B756E', type: 'dashed' },
              label: { formatter: `今日收盘 ${today.close.toFixed(2)}` },
              data: [{ yAxis: today.close }]
            }
          : undefined
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
        itemStyle: { color: '#C9D1CC' }
      }
    ]
  }
}
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd snap-ui
npm run test -- tests/unit/zhongshuOptions.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit in `snap-ui`**

Run:

```bash
git -C snap-ui add app/utils/charts/zhongshuOptions.ts tests/unit/zhongshuOptions.test.ts
git -C snap-ui commit -m "feat: render zhongshu chart options"
```

Expected: commit succeeds.

## Task 5: Build First-Screen Zhongshu UI

**Files:**
- Create: `snap-ui/app/composables/useZhongshuDashboard.ts`
- Create: `snap-ui/app/components/ZhongshuKlineChart.vue`
- Create: `snap-ui/app/components/ZhongshuDetailStrip.vue`
- Create: `snap-ui/app/components/ZhongshuMainlineBadge.vue`
- Create: `snap-ui/app/components/ZhongshuZoneLegend.vue`
- Create: `snap-ui/app/components/ZhongshuStructurePanel.vue`
- Create: `snap-ui/app/components/SnapshotToolbar.vue`
- Create: `snap-ui/app/components/DataStatusBadge.vue`
- Modify: `snap-ui/app/pages/index.vue`

- [ ] **Step 1: Implement dashboard composable**

Create `snap-ui/app/composables/useZhongshuDashboard.ts`:

```ts
import type { SnapshotMode, ZhongshuStructureResponse } from '../types/snapshot'

export function useZhongshuDashboard() {
  const date = ref('')
  const mode = ref<SnapshotMode>('frozen')
  const indexCode = ref('sh000001')
  const range = ref('120')
  const showZones = ref(true)
  const showLabels = ref(true)
  const showTurnoverShare = ref(true)

  const query = computed(() => ({
    date: date.value,
    mode: mode.value,
    index: indexCode.value
  }))

  const enabled = computed(() => /^\d{4}-\d{2}-\d{2}$/.test(date.value))
  const zhongshu = useFetch<ZhongshuStructureResponse>('/api/zhongshu-structure', {
    query,
    immediate: false,
    watch: false
  })

  watch([date, mode, indexCode], () => {
    if (enabled.value) {
      void zhongshu.refresh()
    }
  })

  return {
    date,
    mode,
    indexCode,
    range,
    showZones,
    showLabels,
    showTurnoverShare,
    zhongshu
  }
}
```

- [ ] **Step 2: Create status badge**

Create `snap-ui/app/components/DataStatusBadge.vue`:

```vue
<script setup lang="ts">
import type { DataStatus } from '../types/snapshot'

defineProps<{ status?: DataStatus }>()
</script>

<template>
  <UBadge
    :color="status?.status === 'success' ? 'primary' : status?.status === 'degraded' ? 'warning' : 'error'"
    variant="soft"
    size="sm"
  >
    {{ status?.message || '等待数据' }}
  </UBadge>
</template>
```

- [ ] **Step 3: Create chart component**

Create `snap-ui/app/components/ZhongshuKlineChart.vue`:

```vue
<script setup lang="ts">
import VChart from 'vue-echarts'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, CandlestickChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import type { ZhongshuKlineRow, ZhongshuZone } from '../types/snapshot'
import { buildZhongshuKlineOptions } from '../utils/charts/zhongshuOptions'

use([CanvasRenderer, CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, MarkAreaComponent, MarkLineComponent])

const props = defineProps<{
  rows: ZhongshuKlineRow[]
  zones: ZhongshuZone[]
  selectedZoneId: string
  showZones: boolean
  showLabels: boolean
}>()

const option = computed(() =>
  buildZhongshuKlineOptions(props.rows, props.zones, {
    selectedZoneId: props.selectedZoneId,
    showZones: props.showZones,
    showLabels: props.showLabels
  })
)
</script>

<template>
  <div class="h-[56vh] min-h-[420px] w-full">
    <VChart v-if="rows.length" :option="option" autoresize class="h-full w-full" />
    <div v-else class="flex h-full items-center justify-center rounded-dashboard border border-dashed border-clean-200 text-sm text-clean-600">
      暂无中枢 K 线数据
    </div>
  </div>
</template>
```

- [ ] **Step 4: Create detail strip**

Create `snap-ui/app/components/ZhongshuDetailStrip.vue`:

```vue
<script setup lang="ts">
import type { ZhongshuStructureResponse } from '../types/snapshot'

const props = defineProps<{ data?: ZhongshuStructureResponse | null }>()

const zone = computed(() => props.data?.zones.find((item) => item.id === props.data?.selectedZoneId) || props.data?.zones.at(-1))
</script>

<template>
  <div class="grid gap-2 border-t border-clean-200 pt-3 text-sm md:grid-cols-4 xl:grid-cols-8">
    <div>
      <p class="text-clean-500">结构状态</p>
      <p class="font-semibold text-clean-900">{{ zone?.structureState || '待确认' }}</p>
    </div>
    <div>
      <p class="text-clean-500">中枢周期</p>
      <p class="font-semibold text-clean-900">{{ zone ? `${zone.startDate} ~ ${zone.endDate}` : '-' }}</p>
    </div>
    <div>
      <p class="text-clean-500">ZG / ZD</p>
      <p class="font-semibold text-clean-900">{{ zone ? `${zone.zg.toFixed(2)} / ${zone.zd.toFixed(2)}` : '-' }}</p>
    </div>
    <div>
      <p class="text-clean-500">今日收盘</p>
      <p class="font-semibold text-clean-900">{{ data?.todayPrice?.toFixed(2) || '-' }}</p>
    </div>
    <div>
      <p class="text-clean-500">相对 ZG</p>
      <p class="font-semibold text-clean-900">{{ data?.signal.distToZg == null ? '-' : `${(data.signal.distToZg * 100).toFixed(2)}%` }}</p>
    </div>
    <div>
      <p class="text-clean-500">相对 ZD</p>
      <p class="font-semibold text-clean-900">{{ data?.signal.distToZd == null ? '-' : `${(data.signal.distToZd * 100).toFixed(2)}%` }}</p>
    </div>
    <div>
      <p class="text-clean-500">大主线</p>
      <p class="font-semibold text-wechat-700">{{ zone?.bigMainline || '待确认' }}</p>
    </div>
    <div>
      <p class="text-clean-500">小主线</p>
      <p class="font-semibold text-wechat-700">{{ zone?.smallMainline || '待确认' }}</p>
    </div>
  </div>
</template>
```

- [ ] **Step 5: Create structure panel**

Create `snap-ui/app/components/ZhongshuStructurePanel.vue`:

```vue
<script setup lang="ts">
import type { ZhongshuStructureResponse } from '../types/snapshot'

defineProps<{
  data?: ZhongshuStructureResponse | null
  pending: boolean
  showZones: boolean
  showLabels: boolean
}>()
</script>

<template>
  <section class="rounded-dashboard border border-clean-200 bg-white p-4 shadow-sm">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-xs font-medium text-wechat-700">根本结构</p>
        <h1 class="text-xl font-semibold text-clean-900">日线中枢结构</h1>
      </div>
      <DataStatusBadge :status="data?.status" />
    </div>
    <USkeleton v-if="pending" class="h-[56vh] min-h-[420px] w-full" />
    <ZhongshuKlineChart
      v-else
      :rows="data?.rows || []"
      :zones="data?.zones || []"
      :selected-zone-id="data?.selectedZoneId || ''"
      :show-zones="showZones"
      :show-labels="showLabels"
    />
    <ZhongshuDetailStrip :data="data" />
  </section>
</template>
```

- [ ] **Step 6: Create toolbar**

Create `snap-ui/app/components/SnapshotToolbar.vue`:

```vue
<script setup lang="ts">
const date = defineModel<string>('date', { required: true })
const mode = defineModel<'frozen' | 'replay'>('mode', { required: true })
const indexCode = defineModel<string>('indexCode', { required: true })
const range = defineModel<string>('range', { required: true })
const showZones = defineModel<boolean>('showZones', { required: true })
const showLabels = defineModel<boolean>('showLabels', { required: true })
const showTurnoverShare = defineModel<boolean>('showTurnoverShare', { required: true })

const modes = [
  { label: '官方快照', value: 'frozen' },
  { label: 'Replay', value: 'replay' }
]
const indexes = [
  { label: '上证指数', value: 'sh000001' },
  { label: '深证成指', value: 'sz399001' },
  { label: '创业板指', value: 'sz399006' }
]
const ranges = [
  { label: '近 60 日', value: '60' },
  { label: '近 120 日', value: '120' },
  { label: '全部结构', value: 'all' }
]
</script>

<template>
  <header class="sticky top-0 z-20 border-b border-clean-200 bg-white/95 px-4 py-3 backdrop-blur">
    <div class="mx-auto flex max-w-[1680px] flex-wrap items-center gap-3">
      <UInput v-model="date" type="date" class="w-[160px]" />
      <USelect v-model="mode" :items="modes" class="w-[132px]" />
      <USelect v-model="indexCode" :items="indexes" class="w-[148px]" />
      <USelect v-model="range" :items="ranges" class="w-[132px]" />
      <UCheckbox v-model="showZones" label="中枢框" />
      <UCheckbox v-model="showLabels" label="主线标签" />
      <UCheckbox v-model="showTurnoverShare" label="成交额占比" />
    </div>
  </header>
</template>
```

- [ ] **Step 7: Replace index page with zhongshu-first shell**

Replace `snap-ui/app/pages/index.vue`:

```vue
<script setup lang="ts">
const dashboard = useZhongshuDashboard()
dashboard.date.value = new Date().toISOString().slice(0, 10)
</script>

<template>
  <main class="min-h-screen bg-clean-50 text-clean-900">
    <SnapshotToolbar
      v-model:date="dashboard.date.value"
      v-model:mode="dashboard.mode.value"
      v-model:index-code="dashboard.indexCode.value"
      v-model:range="dashboard.range.value"
      v-model:show-zones="dashboard.showZones.value"
      v-model:show-labels="dashboard.showLabels.value"
      v-model:show-turnover-share="dashboard.showTurnoverShare.value"
    />
    <section class="mx-auto flex max-w-[1680px] flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
      <ZhongshuStructurePanel
        :data="dashboard.zhongshu.data.value"
        :pending="dashboard.zhongshu.pending.value"
        :show-zones="dashboard.showZones.value"
        :show-labels="dashboard.showLabels.value"
      />
    </section>
  </main>
</template>
```

- [ ] **Step 8: Run build and type-check**

Run:

```bash
cd snap-ui
npx vue-tsc --noEmit
npm run build
```

Expected: both pass.

- [ ] **Step 9: Commit in `snap-ui`**

Run:

```bash
git -C snap-ui add app/composables app/components app/pages/index.vue
git -C snap-ui commit -m "feat: add zhongshu first screen"
```

Expected: commit succeeds.

## Task 6: Restore Supporting Mainline And Observation Panels

**Files:**
- Create: `snap-ui/server/utils/snapshot/mainlineSeriesAdapter.ts`
- Create: `snap-ui/server/utils/snapshot/observationPoolAdapter.ts`
- Create: `snap-ui/server/utils/snapshot/stockKlineAdapter.ts`
- Create: `snap-ui/server/api/mainline-series.get.ts`
- Create: `snap-ui/server/api/observation-pool.get.ts`
- Create: `snap-ui/server/api/observation-pool/[code]/kline.get.ts`
- Create: `snap-ui/app/utils/charts/mainlineOptions.ts`
- Create: `snap-ui/app/utils/charts/stockKlineOptions.ts`
- Create: `snap-ui/app/components/MainlineFundingPanel.vue`
- Create: `snap-ui/app/components/ObservationPoolWorkspace.vue`
- Modify: `snap-ui/app/pages/index.vue`
- Test: `snap-ui/tests/unit/mainlineOptions.test.ts`
- Test: `snap-ui/tests/unit/observationPoolAdapter.test.ts`

- [ ] **Step 1: Implement `mainlineOptions` with smooth lines**

Create `snap-ui/tests/unit/mainlineOptions.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildMainlineOptions } from '../../app/utils/charts/mainlineOptions'

describe('buildMainlineOptions', () => {
  it('keeps every line series smooth', () => {
    const option = buildMainlineOptions([
      { date: '2026-04-24', currentMainline: '机器人', sectorTurnover: 1200, marketTurnover: 20000, turnoverSharePct: 6 }
    ] as any)
    const lineSeries = (option.series as any[]).filter((series) => series.type === 'line')
    expect(lineSeries.length).toBeGreaterThan(0)
    expect(lineSeries.every((series) => series.smooth === true)).toBe(true)
  })
})
```

Create `snap-ui/app/utils/charts/mainlineOptions.ts`:

```ts
import type { MainlineSeriesRow } from '../../types/snapshot'

export function buildMainlineOptions(rows: MainlineSeriesRow[]) {
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 48, right: 48, top: 36, bottom: 32 },
    xAxis: { type: 'category', data: rows.map((row) => row.date) },
    yAxis: [{ type: 'value' }, { type: 'value', axisLabel: { formatter: '{value}%' } }],
    series: [
      { name: '主线成交额', type: 'line', smooth: true, data: rows.map((row) => row.sectorTurnover ?? null), lineStyle: { color: '#07C160' } },
      { name: '两市成交额', type: 'line', smooth: true, data: rows.map((row) => row.marketTurnover ?? null), lineStyle: { color: '#AAB5AD' } },
      { name: '主线成交额占比', type: 'line', smooth: true, yAxisIndex: 1, data: rows.map((row) => row.turnoverSharePct ?? null), lineStyle: { color: '#128C45', width: 2 } }
    ]
  }
}
```

- [ ] **Step 2: Create mainline series adapter**

Create `snap-ui/server/utils/snapshot/mainlineSeriesAdapter.ts`:

```ts
import type { MainlineSeriesRow, SourceStatus } from '../../../app/types/snapshot'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord) : []
}

function asNumber(value: unknown): number | null {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

function asText(value: unknown, fallback = ''): string {
  const text = String(value ?? '').trim()
  return text || fallback
}

function rootOf(snapshot: unknown): Record<string, unknown> {
  const root = asRecord(snapshot)
  return asRecord(root.data || root)
}

export function normalizeMainlineSeriesSnapshot(snapshot: unknown): MainlineSeriesRow[] {
  const root = rootOf(snapshot)
  const summary = asRecord(root.mainline_turnover_summary)
  const trendRows = asArray(summary.turnover_share_trend_rows)
  const current = asRecord(root.current_mainline_history_record)
  const currentSector = asRecord(root.current_sector_turnover_snapshot)

  if (trendRows.length > 0) {
    return trendRows.map((row) => ({
      date: asText(row.date || currentSector.date),
      currentMainline: asText(row.currentMainline || row.primary_mainline || row.mainline || current.primary_mainline, '待确认'),
      secondaryMainline: asText(row.secondaryMainline || row.secondary_mainline, '待确认'),
      competitionMainline: asText(row.competitionMainline || row.competition_mainline, '待确认'),
      stateCode: asText(row.stateCode || row.state_code, '观察'),
      sectorName: asText(row.sector_name || row.sectorName || row.mainline, '待确认'),
      sectorTurnover: asNumber(row.sector_turnover || row.sectorTurnover),
      marketTurnover: asNumber(row.total_turnover || row.marketTurnover || row.market_turnover),
      turnoverSharePct: asNumber(row.turnover_share_pct || row.turnoverSharePct),
      shareChangePct: asNumber(row.share_change_pct || row.shareChangePct),
      sourceStatus: 'success' as SourceStatus,
      sourceMessage: '已读取主线成交额趋势'
    }))
  }

  return [
    {
      date: asText(currentSector.date || root.date),
      currentMainline: asText(current.primary_mainline || current.leading_line, '待确认'),
      secondaryMainline: asText(current.secondary_mainline, '待确认'),
      competitionMainline: asText(current.competition_mainline, '待确认'),
      stateCode: asText(current.state_code, '观察'),
      sectorName: asText(currentSector.sector_name, '待确认'),
      sectorTurnover: asNumber(currentSector.sector_turnover),
      marketTurnover: asNumber(currentSector.total_turnover),
      turnoverSharePct: asNumber(currentSector.turnover_share_pct),
      shareChangePct: null,
      sourceStatus: currentSector.sector_turnover ? 'success' : 'missing',
      sourceMessage: currentSector.sector_turnover ? '已读取当前主线成交额' : '快照缺少主线成交额字段'
    }
  ]
}
```

- [ ] **Step 3: Create observation pool and stock K-line adapters**

Create `snap-ui/tests/unit/observationPoolAdapter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { normalizeObservationPool } from '../../server/utils/snapshot/observationPoolAdapter'
import { normalizeStockKline } from '../../server/utils/snapshot/stockKlineAdapter'

describe('observation pool adapters', () => {
  it('groups pool rows and marks big/small mainline matches', () => {
    const snapshot = {
      data: {
        appendix_c: {
          current_stock_monitoring_pool: [
            { stock_name: '成飞集成', stock_code: '002190', source_pool: '主线核心', sector: '机器人', current_action: '观察承接' },
            { stock_name: '光启技术', stock_code: '002625', source_pool: '跨线观察', sector: '军工', current_action: '只看不追' }
          ]
        }
      }
    }

    const result = normalizeObservationPool(snapshot, {
      date: '2026-04-24',
      bigMainline: '机器人',
      smallMainline: '低空经济'
    })

    expect(result.groups[0].rows[0]).toMatchObject({ stockCode: '002190', poolGroup: 'main', status: 'success' })
    expect(result.groups[1].rows[0]).toMatchObject({ stockCode: '002625', poolGroup: 'secondary' })
  })

  it('does not fabricate stock kline rows', () => {
    const result = normalizeStockKline({ data: {} }, { date: '2026-04-24', stockCode: '002190' })
    expect(result.rows).toEqual([])
    expect(result.status.status).toBe('missing')
  })
})
```

Create `snap-ui/server/utils/snapshot/observationPoolAdapter.ts`:

```ts
import type { ObservationPoolGroup, ObservationPoolResponse, ObservationPoolStock } from '../../../app/types/snapshot'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord) : []
}

function text(value: unknown, fallback = '') {
  const result = String(value ?? '').trim()
  return result || fallback
}

function rootOf(snapshot: unknown): Record<string, unknown> {
  const root = asRecord(snapshot)
  return asRecord(root.data || root)
}

function groupFor(sourcePool: string): ObservationPoolStock['poolGroup'] {
  return sourcePool.includes('核心') || sourcePool.includes('备选') ? 'main' : 'secondary'
}

export function normalizeObservationPool(
  snapshot: unknown,
  options: { date: string; bigMainline: string; smallMainline: string }
): ObservationPoolResponse {
  const root = rootOf(snapshot)
  const appendixC = asRecord(root.appendix_c)
  const rawRows = [
    ...asArray(appendixC.current_stock_monitoring_pool),
    ...asArray(root.core_stocks),
    ...asArray(root.secondary_stocks),
    ...asArray(root.crossline_observation_stocks),
    ...asArray(root.gem_observation_stocks),
    ...asArray(root.generic_watch_stocks)
  ]

  const seen = new Set<string>()
  const rows: ObservationPoolStock[] = []
  for (const row of rawRows) {
    const stockCode = text(row.stock_code || row.code)
    if (!stockCode || seen.has(stockCode)) continue
    seen.add(stockCode)
    const sourcePool = text(row.source_pool || row.pool || row.group, '普通观察')
    const sector = text(row.sector || row.mainline)
    rows.push({
      stockName: text(row.stock_name || row.name, stockCode),
      stockCode,
      sourcePool,
      poolGroup: groupFor(sourcePool),
      currentAction: text(row.current_action || row.action || row.currentAction, '观察'),
      status: sector && (sector.includes(options.bigMainline) || sector.includes(options.smallMainline)) ? 'success' : 'degraded'
    })
  }

  const groups: ObservationPoolGroup[] = [
    { label: '主线核心 / 备选', poolGroup: 'main', rows: rows.filter((row) => row.poolGroup === 'main') },
    { label: '跨线 / 普通观察', poolGroup: 'secondary', rows: rows.filter((row) => row.poolGroup === 'secondary') }
  ]

  return {
    date: options.date,
    groups,
    status: rows.length
      ? { status: 'success', message: '已读取观察池', sourceField: 'appendix_c.current_stock_monitoring_pool' }
      : { status: 'missing', message: '该日期无观察池', sourceField: 'appendix_c.current_stock_monitoring_pool' }
  }
}
```

Create `snap-ui/server/utils/snapshot/stockKlineAdapter.ts`:

```ts
import type { KlineRow, StockKlineResponse } from '../../../app/types/snapshot'

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.map(asRecord) : []
}

function num(value: unknown): number | null {
  const result = Number(value)
  return Number.isFinite(result) ? result : null
}

function txt(value: unknown, fallback = '') {
  const result = String(value ?? '').trim()
  return result || fallback
}

export function normalizeStockKline(snapshot: unknown, options: { date: string; stockCode: string }): StockKlineResponse {
  const root = asRecord(asRecord(snapshot).data || snapshot)
  const rowsByCode = asRecord(root.stock_klines || root.stockKlines)
  const rows: KlineRow[] = asArray(rowsByCode[options.stockCode]).map((row) => ({
    date: txt(row.date),
    open: num(row.open) ?? 0,
    close: num(row.close) ?? 0,
    low: num(row.low) ?? 0,
    high: num(row.high) ?? 0,
    volume: num(row.volume),
    dailyChangePct: num(row.daily_change_pct || row.dailyChangePct),
    cumulativeChangePct: num(row.cumulative_change_pct || row.cumulativeChangePct)
  })).filter((row) => row.date && row.open && row.close && row.low && row.high)

  return {
    date: options.date,
    stockCode: options.stockCode,
    stockName: options.stockCode,
    source: rows.length ? `stock_klines.${options.stockCode}` : '',
    rows,
    status: rows.length
      ? { status: 'success', message: '已读取个股 K 线', sourceField: `stock_klines.${options.stockCode}` }
      : { status: 'missing', message: '暂无 K 线数据', sourceField: `stock_klines.${options.stockCode}` }
  }
}
```

- [ ] **Step 4: Create supporting API endpoints**

Create `snap-ui/server/api/mainline-series.get.ts`:

```ts
import { getQuery } from 'h3'
import { resolveDailyReportRoot } from '../utils/sourcePath'
import { listSnapshotRefs } from '../utils/snapshot/scanner'
import { loadSnapshotForDate } from '../utils/snapshot/loadSnapshot'
import { normalizeMainlineSeriesSnapshot } from '../utils/snapshot/mainlineSeriesAdapter'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const mode = String(query.mode || 'frozen')
  const root = resolveDailyReportRoot()
  const refs = (await listSnapshotRefs(root)).refs.filter((ref) => mode === 'auto' || ref.mode === mode).slice(-30)
  const rows = []
  for (const ref of refs) {
    const snapshot = await loadSnapshotForDate(root, ref.date, ref.mode)
    rows.push(...normalizeMainlineSeriesSnapshot(snapshot))
  }
  return { rows }
})
```

Create `snap-ui/server/api/observation-pool.get.ts`:

```ts
import { getQuery } from 'h3'
import type { SnapshotMode } from '../../app/types/snapshot'
import { resolveDailyReportRoot } from '../utils/sourcePath'
import { loadSnapshotForDate } from '../utils/snapshot/loadSnapshot'
import { normalizeObservationPool } from '../utils/snapshot/observationPoolAdapter'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const date = String(query.date || '')
  const mode = String(query.mode || 'frozen') as SnapshotMode
  const root = resolveDailyReportRoot()
  const snapshot = await loadSnapshotForDate(root, date, mode)
  return normalizeObservationPool(snapshot, {
    date,
    bigMainline: String(query.bigMainline || ''),
    smallMainline: String(query.smallMainline || '')
  })
})
```

Create `snap-ui/server/api/observation-pool/[code]/kline.get.ts`:

```ts
import { getQuery, getRouterParam } from 'h3'
import type { SnapshotMode } from '../../../app/types/snapshot'
import { resolveDailyReportRoot } from '../../utils/sourcePath'
import { loadSnapshotForDate } from '../../utils/snapshot/loadSnapshot'
import { normalizeStockKline } from '../../utils/snapshot/stockKlineAdapter'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const date = String(query.date || '')
  const mode = String(query.mode || 'frozen') as SnapshotMode
  const stockCode = String(getRouterParam(event, 'code') || '')
  const root = resolveDailyReportRoot()
  const snapshot = await loadSnapshotForDate(root, date, mode)
  return normalizeStockKline(snapshot, { date, stockCode })
})
```

Run:

```bash
cd snap-ui
npm run test -- tests/unit/mainlineOptions.test.ts tests/unit/observationPoolAdapter.test.ts
```

Expected: PASS with tests covering grouped pools and no fake K-line rows.

- [ ] **Step 5: Add supporting panels under the zhongshu panel**

The page order must be:

1. `ZhongshuStructurePanel`
2. `MainlineFundingPanel`
3. `ObservationPoolWorkspace`

The supporting panels must not push the zhongshu panel out of first-screen priority.

- [ ] **Step 6: Commit in `snap-ui`**

Run:

```bash
git -C snap-ui add app server tests
git -C snap-ui commit -m "feat: add zhongshu supporting analysis panels"
```

Expected: commit succeeds.

## Task 7: Visual Verification And Local Server

**Files:**
- Create: `snap-ui/tests/e2e/dashboard.spec.ts`

- [ ] **Step 1: Add Playwright smoke test**

Create `snap-ui/tests/e2e/dashboard.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

test('first screen prioritizes zhongshu structure', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '日线中枢结构' })).toBeVisible()
  await expect(page.getByText('根本结构')).toBeVisible()
})
```

- [ ] **Step 2: Add Playwright config if missing**

Create `snap-ui/playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:3040',
    reuseExistingServer: true,
    timeout: 120_000
  },
  use: {
    baseURL: 'http://127.0.0.1:3040'
  }
})
```

- [ ] **Step 3: Run full verification**

Run:

```bash
cd snap-ui
npm run test
npx vue-tsc --noEmit
npm run build
npm run test:e2e
```

Expected: all pass. Build may show sourcemap warnings from dependencies; those are acceptable only if the build exits successfully.

- [ ] **Step 4: Start local dev server for user review**

Run:

```bash
cd snap-ui
npm run dev
```

Expected URL:

```text
http://127.0.0.1:3040
```

Keep the server running only if the user wants to inspect the UI immediately.

- [ ] **Step 5: Commit verification artifacts**

Run:

```bash
git -C snap-ui add tests/e2e/dashboard.spec.ts playwright.config.ts
git -C snap-ui commit -m "test: verify zhongshu dashboard first screen"
```

Expected: commit succeeds.

## Parent Repo Completion

- [ ] **Step 1: Verify parent only tracks docs and optional helper**

Run:

```bash
git status --short
git diff --name-only
```

Expected: only this plan, the design spec, and optional parent helper/test files appear for this work. Do not stage unrelated dirty files.

- [ ] **Step 2: Commit parent docs**

Run:

```bash
git add docs/superpowers/specs/2026-04-27-snapshot-visual-analysis-ui-design.md docs/superpowers/plans/2026-04-27-snapshot-visual-analysis-ui-implementation-plan.md
git commit -m "docs: recenter snapshot UI on zhongshu structure"
```

Expected: parent commit succeeds without staging unrelated files.
