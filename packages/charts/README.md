# @crewgraphs/charts

Hand-rolled SVG chart kit for CrewGraphs. Renders a single annual financial
series (revenue, expenses, a derived metric…) for a nonprofit rowing club as a
quiet, printed-program line or bar chart. Built for **tiny data** — ≤ ~8 annual
points, one series per chart — and for correctness about *missing vs zero vs
amended*, which is a product rule, not a nicety.

Dependencies: `d3-scale`, `d3-shape`, and `react` (peer). No fonts bundled, no
CSS file to import, no runtime theme engine.

## Exports

| Export | Kind | Purpose |
| --- | --- | --- |
| `AnnualSeriesChart` | client | One series as a static SVG `line` or `bar` chart. |
| `SeriesTable` | server | The accessible data twin — a real `<table>`. |
| `ChartWithTable` | client | `<figure>` with a Chart \| Table toggle over one series. |
| `formatUSD` / `formatCount` / `formatValue` | fn | Exact + `compact` number formatting. |
| `qualityLabel` | fn | Quality-state → wording ("under_review" → "under review"). |
| `buildGeometry` | fn | Pure geometry (scales, paths, marks) — the testable core. |
| types | — | `AnnualSeries`, `AnnualPoint`, `QualityState`, `PointActivateHandler`, … |

```tsx
import { ChartWithTable, type AnnualSeries } from "@crewgraphs/charts";

const series: AnnualSeries = {
  key: "concept:total_revenue",
  label: "Total revenue",
  unit: "USD",
  points: [
    { tax_year: 2022, fy_end: "2022-12-31", value: 1_250_000, quality_state: "verified", is_amended: false, label: "FY2022" },
    { tax_year: 2023, fy_end: "2023-12-31", value: null,      quality_state: "unavailable", is_amended: false, label: "FY2023" },
    // …
  ],
};

<ChartWithTable
  kind="line"
  series={series}
  ariaSummary="Total revenue: $1.25M in FY2022, no filing in FY2023."
  onPointActivate={(point) => openSourceDrawer(series.key, point.tax_year)}
/>;
```

`AnnualSeries` is trivially derivable from `read.org_financial_series` rows
joined with `org_filing_coverage`; a point maps 1:1 onto a `SourceRef.period`
(see `@crewgraphs/contracts`).

## Interaction model (the important part)

**The SVG is decorative; the interactive layer is real HTML.**

- The `<svg>` carries `role="img"` + `aria-label={ariaSummary}`. To assistive
  tech it is a **single labelled image** — one honest sentence — not dozens of
  traversable nodes.
- Over the SVG sits an absolutely-positioned overlay of **real `<button>`
  elements**, one per period, aligned to each mark. No `foreignObject`, no
  faux-ARIA on SVG shapes: native keyboard focus, native screen-reader button
  semantics. Buttons are positioned by **percentage** so they track the SVG as
  it scales to 100% container width.
- Each button's accessible name is the full story, e.g.
  `"FY2023 Total revenue $1,250,000, verified"` (with ` (amended)` appended when
  applicable). A **missing** year is a `disabled` button named
  `"FY2021 — no filing"` — discoverable, never activatable.
- Activating a value point fires `onPointActivate(point, series)`. **The kit owns
  no drawer logic.** It is also decoupled from `@crewgraphs/contracts`: the point
  carries no `SourceRef`. The consumer keeps the provenance map and looks it up
  by `(series.key, point.tax_year)` to open the SourceDrawer.

### Rendering & the RSC boundary

`AnnualSeriesChart` and `ChartWithTable` are `"use client"` — but a client
component still **server-renders to static SVG** (the geometry is deterministic,
computed in a fixed viewBox with no DOM measurement, so server and client HTML
are byte-identical). Hydration only wires the point buttons and the toggle.
`SeriesTable` is a **pure server component** (no JS shipped).

> Consuming Next.js app: add `"@crewgraphs/charts"` to `transpilePackages` in
> `next.config.ts` (the package ships raw `.tsx` via `exports: "./src/index.ts"`,
> exactly like `@crewgraphs/contracts`).

### `ChartWithTable` accessibility choice

Both views live in the DOM at once. The chart's SVG **always** carries the
`ariaSummary`, so a screen-reader user gets the gist even in chart view; the full
tabular data is one keypress away. The inactive view is removed from the tree
with the **`hidden` attribute** (so its controls leave the tab order), not merely
`display:none`. Toggle controls are real `<button>`s with `aria-pressed`.

## Data semantics (non-negotiable)

| State | Detection | Line | Bar | Table cell |
| --- | --- | --- | --- | --- |
| **Missing** (no filing) | `value === null` | line **breaks** (d3 `defined`), never interpolated; faint dashed slot guide | hatched empty slot placeholder | the quality word (e.g. "unavailable") — never `0`, never blank |
| **Zero** (a real value) | `value === 0` | dot on the baseline | 2px nub at the baseline | `$0` |
| **Amended** | `is_amended` | apex-up **triangle** overlay + `(amended)` suffix | same | "amended" |
| **partial / under_review** | `quality_state` | **hollow / dashed** dot + quality in the name | hollow/dashed bar | quality word |

Quality is never encoded by colour alone — shape (hollow/dashed), a marker
(triangle), and words carry it. `partial` and `under_review` are, per spec, not
ranking-eligible; that gating lives in the read model, not here.

## Theming

Colours and the numeral font come from CSS custom properties (with print-quiet
fallbacks), so the app theme — including dark mode — drives everything. No colours
are hard-coded past these fallbacks.

| Variable | Fallback | Role |
| --- | --- | --- |
| `--color-river` | `#0E1B2C` | ink — line, bars, baseline, axis text emphasis |
| `--color-paper` | `#F7F9FB` | paper — hollow-mark fills, active-toggle text |
| `--color-hairline` | `#D9E2EA` | hairlines, hatch, gap guides |
| `--color-buoy` | `#E85D26` | accent — focused/active point ring, active toggle |
| `--color-river-muted` | `#5B6B7A` | axis tick + caption text |
| `--font-data` | `ui-monospace, …` | tabular mono numerals (axes + table) |

Design language: ink on paper, no gridline soup (baseline + at most 3
hairlines), tabular mono numerals, quiet.

## Development

```bash
bun install            # from repo root
cd packages/charts
bun run typecheck      # tsc --noEmit
bun run test           # vitest (jsdom + @testing-library/react)
```

Tests are offline and cover: the broken line path at a gap, hatched slot + a
"no filing" accessible label, zero rendered distinct from a gap, the amended
marker + suffix, full accessible button names firing `onPointActivate`, the
table rendering `null` as its quality word, and the toggle flipping visibility
with `aria-pressed`.
