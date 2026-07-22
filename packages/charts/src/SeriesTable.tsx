import { formatValue, qualityLabel } from "./format";
import type { AnnualSeries } from "./types";

export interface SeriesTableProps {
  series: AnnualSeries;
  /** Optional visible caption; defaults to the series label + unit. */
  caption?: string;
  /** Hide the caption visually while keeping it for screen readers. */
  captionVisuallyHidden?: boolean;
}

const C = {
  ink: "var(--color-river, #0E1B2C)",
  hairline: "var(--color-hairline, #D9E2EA)",
  muted: "var(--color-river-muted, #5B6B7A)"
} as const;

const DATA_FONT = "var(--font-data, ui-monospace, SFMono-Regular, Menlo, monospace)";

const srOnly: React.CSSProperties = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0
};

const th: React.CSSProperties = {
  textAlign: "left",
  fontWeight: 600,
  fontSize: 12,
  color: C.muted,
  padding: "6px 12px",
  borderBottom: `1px solid ${C.hairline}`
};

const td: React.CSSProperties = {
  fontSize: 13,
  color: C.ink,
  padding: "6px 12px",
  borderBottom: `1px solid ${C.hairline}`
};

const numTd: React.CSSProperties = {
  ...td,
  textAlign: "right",
  fontFamily: DATA_FONT,
  fontVariantNumeric: "tabular-nums"
};

/**
 * The accessibility twin of every chart: a real `<table>` carrying the same
 * data. A null value renders the quality word ("unavailable"), never `0` and
 * never blank — the honest missing-vs-zero rule from the spec. Values are
 * right-aligned tabular mono numerals so columns line up like a printed program.
 */
export function SeriesTable({ series, caption, captionVisuallyHidden }: SeriesTableProps) {
  const captionText = caption ?? `${series.label} by fiscal year (${series.unit === "USD" ? "US dollars" : "count"})`;

  return (
    <table
      className="cg-table"
      style={{ borderCollapse: "collapse", width: "100%", color: C.ink }}
    >
      <caption style={captionVisuallyHidden ? srOnly : { textAlign: "left", fontSize: 12, color: C.muted, padding: "0 0 8px" }}>
        {captionText}
      </caption>
      <thead>
        <tr>
          <th scope="col" style={th}>Period</th>
          <th scope="col" style={{ ...th, textAlign: "right" }}>Value</th>
          <th scope="col" style={th}>Quality</th>
          <th scope="col" style={th}>Amended</th>
        </tr>
      </thead>
      <tbody>
        {series.points.map((p) => {
          const isMissing = p.value === null;
          const valueCell = isMissing
            ? qualityLabel(p.quality_state)
            : formatValue(p.value as number, series.unit);
          return (
            <tr key={p.tax_year} data-year={p.tax_year} data-missing={isMissing ? "" : undefined}>
              <th scope="row" style={{ ...td, fontWeight: 500, textAlign: "left" }}>{p.label}</th>
              <td
                style={numTd}
                data-value={isMissing ? "null" : String(p.value)}
                {...(isMissing ? { "aria-label": qualityLabel(p.quality_state) } : {})}
              >
                {valueCell}
              </td>
              <td style={td}>{qualityLabel(p.quality_state)}</td>
              <td style={td}>
                {p.is_amended ? (
                  <span data-testid="cg-table-amended">amended</span>
                ) : (
                  <span aria-hidden="true" style={{ color: C.muted }}>—</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
