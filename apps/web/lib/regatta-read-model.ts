import { resultRefSchema, type ResultRef } from "@crewgraphs/contracts";

/**
 * Pure mappers for the regatta-activity read model (no I/O — the seam
 * `regatta-data.ts` does the querying). Rows come from the long-form
 * `read.org_regatta_result` table (one row per entry-metric); this module
 * re-parses every `source_ref` through the shared contract (an invalid ref
 * throws rather than rendering) and regroups rows into
 * season → regatta → entry lines for the profile section.
 */

export interface RegattaResultRow {
  season: number;
  regatta_key: string;
  regatta_name: string;
  regatta_date: string | null;
  venue: string | null;
  source_key: string;
  event_key: string;
  event_name: string;
  boat_class: string | null;
  round: string | null;
  crew_label: string | null;
  crew: unknown;
  metric_key: string;
  status: string;
  source_ref: unknown;
}

export interface CrewMember {
  role: string;
  name: string;
}

/** One boat's line in a regatta: an entry plus its provenanced metrics. */
export interface EntryLine {
  eventKey: string;
  eventName: string;
  boatClass: string | null;
  round: string | null;
  crewLabel: string | null;
  crew: CrewMember[];
  status: string;
  metrics: Partial<Record<string, ResultRef>>;
}

export interface RegattaBlock {
  regattaKey: string;
  name: string;
  date: string | null;
  venue: string | null;
  sourceKey: string;
  providerUrl: string | null;
  entries: EntryLine[];
}

export interface SeasonBlock {
  season: number;
  regattas: RegattaBlock[];
}

/** Provider attribution labels for the section footer + drawers. */
export const RESULT_SOURCE_LABELS: Record<string, string> = {
  herenow: "HereNow Sports",
  time_team: "Time-Team (USRowing)",
  regattatiming: "Regatta Timing",
  row2k: "row2k",
  crewtimer: "CrewTimer"
};

/**
 * Group long-form rows into seasons (desc) → regattas (date desc) → entry
 * lines (event order as published). Metrics for the same entry collapse onto
 * one line keyed by metric_key; every ref is contract-parsed here.
 */
export function groupRegattaActivity(rows: RegattaResultRow[]): SeasonBlock[] {
  const seasons = new Map<number, Map<string, RegattaBlock>>();

  for (const row of rows) {
    const ref = resultRefSchema.parse(row.source_ref);
    let regattas = seasons.get(row.season);
    if (!regattas) {
      regattas = new Map();
      seasons.set(row.season, regattas);
    }
    let regatta = regattas.get(row.regatta_key);
    if (!regatta) {
      regatta = {
        regattaKey: row.regatta_key,
        name: row.regatta_name,
        date: row.regatta_date,
        venue: row.venue,
        sourceKey: row.source_key,
        providerUrl: ref.source.provider_url,
        entries: []
      };
      regattas.set(row.regatta_key, regatta);
    }

    const entryId = `${row.event_key}::${row.crew_label ?? ""}`;
    let entry = regatta.entries.find(
      (line) => `${line.eventKey}::${line.crewLabel ?? ""}` === entryId
    );
    if (!entry) {
      entry = {
        eventKey: row.event_key,
        eventName: row.event_name,
        boatClass: row.boat_class,
        round: row.round,
        crewLabel: row.crew_label,
        crew: parseCrew(row.crew),
        status: row.status,
        metrics: {}
      };
      regatta.entries.push(entry);
    }
    entry.metrics[row.metric_key] = ref;
  }

  return [...seasons.entries()]
    .sort(([a], [b]) => b - a)
    .map(([season, regattas]) => ({
      season,
      regattas: [...regattas.values()].sort((a, b) =>
        (b.date ?? "").localeCompare(a.date ?? "")
      )
    }));
}

function parseCrew(value: unknown): CrewMember[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (member): member is CrewMember =>
      typeof member === "object" &&
      member !== null &&
      typeof (member as CrewMember).role === "string" &&
      typeof (member as CrewMember).name === "string"
  );
}

/** 423.35 → "7:03.35"; 3723.45 → "1:02:03.45". Hundredths kept as published. */
export function formatRaceSeconds(totalSeconds: number): string {
  const sign = totalSeconds < 0 ? "-" : "";
  const abs = Math.abs(totalSeconds);
  const hundredths = Math.round(abs * 100) % 100;
  const wholeSeconds = Math.floor(abs);
  const hours = Math.floor(wholeSeconds / 3600);
  const minutes = Math.floor((wholeSeconds % 3600) / 60);
  const seconds = wholeSeconds % 60;
  const ss = String(seconds).padStart(2, "0");
  const hh = String(hundredths).padStart(2, "0");
  if (hours > 0) {
    return `${sign}${hours}:${String(minutes).padStart(2, "0")}:${ss}.${hh}`;
  }
  return `${sign}${minutes}:${ss}.${hh}`;
}

/** Format a result value per its unit for the compact table cell. */
export function formatResultValue(ref: ResultRef): string {
  if (ref.value === null) return "—";
  switch (ref.unit) {
    case "seconds":
    case "handicap_seconds":
      return formatRaceSeconds(ref.value);
    case "margin_seconds":
      return `+${formatRaceSeconds(ref.value)}`;
    case "rank": {
      const place = Math.trunc(ref.value);
      return `${place}${ordinalSuffix(place)}`;
    }
    default:
      return String(ref.value);
  }
}

function ordinalSuffix(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return "th";
  switch (n % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}
