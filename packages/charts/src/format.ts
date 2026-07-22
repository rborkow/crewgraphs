import type { QualityState, SeriesUnit } from "./types";

/**
 * Number formatting. Two registers:
 * - `compact` for axis ticks ("$1.3M", "1.2K") — terse, approximate;
 * - exact for point labels and the table ("$1,250,000", "1,204") — precise.
 *
 * Currency is whole-dollar (nonprofit filings carry no cents); counts are
 * integers. Both are locale-stable ("en-US") so server and client render byte
 * identical strings (no hydration drift).
 */

const usdExact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

const usdCompact = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1
});

const countExact = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0
});

const countCompact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1
});

export interface FormatOptions {
  /** Axis register: terse and approximate. Default `false` (exact). */
  compact?: boolean;
}

export function formatUSD(value: number, opts: FormatOptions = {}): string {
  return (opts.compact ? usdCompact : usdExact).format(value);
}

export function formatCount(value: number, opts: FormatOptions = {}): string {
  return (opts.compact ? countCompact : countExact).format(value);
}

/** Unit-aware formatter used by marks, labels, axes and the table. */
export function formatValue(
  value: number,
  unit: SeriesUnit,
  opts: FormatOptions = {}
): string {
  return unit === "USD" ? formatUSD(value, opts) : formatCount(value, opts);
}

/** Screen-reader / table wording for a quality state (never color-alone). */
export function qualityLabel(state: QualityState): string {
  switch (state) {
    case "verified":
      return "verified";
    case "derived":
      return "derived";
    case "partial":
      return "partial";
    case "unavailable":
      return "unavailable";
    case "under_review":
      return "under review";
  }
}
