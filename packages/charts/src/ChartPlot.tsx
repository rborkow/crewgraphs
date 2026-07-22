"use client";

import { useId } from "react";
import { buildGeometry, type Mark } from "./geometry";
import type { AnnualSeries, ChartKind, PointActivateHandler } from "./types";

/**
 * Internal SVG + overlay renderer shared by `AnnualSeriesChart` and
 * `ChartWithTable`.
 *
 * Interaction model (documented in the README): the SVG is a single decorative
 * `role="img"` labelled by `ariaSummary`, so assistive tech reads one honest
 * sentence instead of traversing dozens of marks. The focusable, activatable
 * layer is a set of REAL HTML `<button>`s absolutely positioned over each mark
 * — native keyboard + screen-reader semantics, no `foreignObject`, no faux-ARIA
 * on SVG nodes. Buttons are placed by percentage so they track the SVG as it
 * scales to container width. A missing year is a `disabled` button carrying a
 * "… — no filing" name: discoverable, never activatable.
 */

const C = {
  ink: "var(--color-river, #0E1B2C)",
  paper: "var(--color-paper, #F7F9FB)",
  hairline: "var(--color-hairline, #D9E2EA)",
  accent: "var(--color-buoy, #E85D26)",
  muted: "var(--color-river-muted, #5B6B7A)"
} as const;

const DATA_FONT = "var(--font-data, ui-monospace, SFMono-Regular, Menlo, monospace)";

export interface ChartPlotProps {
  kind: ChartKind;
  series: AnnualSeries;
  ariaSummary: string;
  height?: number;
  width?: number;
  onPointActivate?: PointActivateHandler;
}

export function ChartPlot({
  kind,
  series,
  ariaSummary,
  height = 220,
  width = 640,
  onPointActivate
}: ChartPlotProps) {
  const rawId = useId();
  const hatchId = `cg-hatch-${rawId.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const g = buildGeometry(series, { kind, width, height });

  return (
    <div className="cg-plot" style={{ position: "relative", width: "100%" }}>
      <style>{
        `.cg-point{-webkit-tap-highlight-color:transparent}` +
        `.cg-point:focus{outline:none}` +
        `.cg-point:focus-visible{outline:2px solid ${C.accent};outline-offset:1px;border-radius:9999px}`
      }</style>

      <svg
        viewBox={`0 0 ${g.width} ${g.height}`}
        role="img"
        aria-label={ariaSummary}
        preserveAspectRatio="xMidYMid meet"
        data-kind={kind}
        data-testid="cg-svg"
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
      >
        <defs>
          <pattern
            id={hatchId}
            width={6}
            height={6}
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1={0} y1={0} x2={0} y2={6} stroke={C.hairline} strokeWidth={1.4} />
          </pattern>
        </defs>

        {/* Hairlines — baseline + at most 3, no gridline soup. */}
        {g.hairlines.map((t) => (
          <line
            key={`h-${t.value}`}
            x1={g.plot.left}
            x2={g.width - g.plot.right}
            y1={t.y}
            y2={t.y}
            stroke={C.hairline}
            strokeWidth={1}
          />
        ))}
        <line
          x1={g.plot.left}
          x2={g.width - g.plot.right}
          y1={g.baselineY}
          y2={g.baselineY}
          stroke={C.ink}
          strokeWidth={1.25}
          data-testid="cg-baseline"
        />

        {/* Y tick labels (compact, tabular). */}
        {g.yTicks.map((t) => (
          <text
            key={`yt-${t.value}`}
            x={g.plot.left - 8}
            y={t.y}
            textAnchor="end"
            dominantBaseline="middle"
            style={{ fontFamily: DATA_FONT, fontVariantNumeric: "tabular-nums", fontSize: 11, fill: C.muted }}
          >
            {t.label}
          </text>
        ))}

        {/* X (year) labels. */}
        {g.xTicks.map((t) => (
          <text
            key={`xt-${t.label}`}
            x={t.x}
            y={g.height - 10}
            textAnchor="middle"
            style={{ fontFamily: DATA_FONT, fontVariantNumeric: "tabular-nums", fontSize: 11, fill: C.muted }}
          >
            {t.label}
          </text>
        ))}

        {/* Line path — with true gaps at missing years. */}
        {kind === "line" && g.linePath ? (
          <path
            d={g.linePath}
            fill="none"
            stroke={C.ink}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            data-testid="cg-line"
            data-mark="line"
          />
        ) : null}

        {/* Marks. */}
        {g.marks.map((m) => (
          <MarkShape key={`m-${m.tax_year}`} kind={kind} mark={m} hatchId={hatchId} plot={g.plot} baselineY={g.baselineY} />
        ))}
      </svg>

      {/* Accessible interactive overlay — one real button per period. */}
      <div className="cg-overlay" style={{ position: "absolute", inset: 0 }}>
        {g.marks.map((m) => (
          <button
            key={`b-${m.tax_year}`}
            type="button"
            className="cg-point"
            disabled={m.isMissing}
            aria-label={m.accessibleName}
            title={m.accessibleName}
            data-point-key={m.tax_year}
            data-quality={m.quality}
            data-mark={m.isMissing ? "missing" : m.isZero ? "zero" : "value"}
            {...(m.isAmended ? { "data-amended": "" } : {})}
            onClick={m.isMissing ? undefined : () => onPointActivate?.(series.points[m.index], series)}
            style={{
              position: "absolute",
              left: `${m.xPct}%`,
              top: `${m.yPct}%`,
              width: 26,
              height: 26,
              transform: "translate(-50%, -50%)",
              margin: 0,
              padding: 0,
              border: 0,
              background: "transparent",
              cursor: m.isMissing ? "default" : "pointer"
            }}
          />
        ))}
      </div>
    </div>
  );
}

interface MarkShapeProps {
  kind: ChartKind;
  mark: Mark;
  hatchId: string;
  plot: { top: number; right: number; bottom: number; left: number };
  baselineY: number;
}

function MarkShape({ kind, mark: m, hatchId, plot }: MarkShapeProps) {
  const amended = m.amendedMarker ? (
    <path d={m.amendedMarker} fill={C.ink} data-testid="cg-amended" aria-hidden="true" />
  ) : null;

  if (kind === "bar") {
    if (m.isMissing && m.missingRect) {
      return (
        <rect
          x={m.missingRect.x}
          y={m.missingRect.y}
          width={m.missingRect.width}
          height={m.missingRect.height}
          fill={`url(#${hatchId})`}
          stroke={C.hairline}
          strokeWidth={1}
          strokeDasharray="3 3"
          data-mark="missing"
          data-year={m.tax_year}
        />
      );
    }
    return (
      <g>
        <path
          d={m.barPath ?? ""}
          fill={m.isHollow ? C.paper : C.ink}
          stroke={m.isHollow ? C.ink : "none"}
          strokeWidth={m.isHollow ? 1.4 : 0}
          strokeDasharray={m.isHollow ? "4 3" : undefined}
          data-mark={m.isZero ? "zero" : "bar"}
          data-quality={m.quality}
          {...(m.isAmended ? { "data-amended": "" } : {})}
          data-year={m.tax_year}
        />
        {amended}
      </g>
    );
  }

  // Line mode marks.
  if (m.isMissing) {
    return (
      <line
        x1={m.cx}
        x2={m.cx}
        y1={plot.top}
        y2={plot.bottom}
        stroke={C.hairline}
        strokeWidth={1}
        strokeDasharray="2 3"
        data-mark="missing"
        data-year={m.tax_year}
      />
    );
  }
  return (
    <g>
      <circle
        cx={m.cx}
        cy={m.cy}
        r={4}
        fill={m.isHollow ? C.paper : C.ink}
        stroke={m.isHollow ? C.ink : "none"}
        strokeWidth={m.isHollow ? 1.4 : 0}
        strokeDasharray={m.isHollow ? "3 2" : undefined}
        data-mark={m.isZero ? "zero" : "point"}
        data-quality={m.quality}
        {...(m.isAmended ? { "data-amended": "" } : {})}
        data-year={m.tax_year}
      />
      {amended}
    </g>
  );
}
