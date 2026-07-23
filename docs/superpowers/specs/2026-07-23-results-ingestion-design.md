# CrewGraphs Results Ingestion Design

**Date:** 2026-07-23
**Status:** Approved
**Source research:** `docs/superpowers/research/2026-07-23-results-timing-providers.md` · **Supersedes** the MVP spec's "every results source is permission-gated" premise for the timing-provider layer.
**Companion policy:** `docs/superpowers/specs/2026-07-23-athlete-pii-policy.md`
**Living plan:** `docs/superpowers/plans/2026-07-23-results-ingestion.md`

## Problem

The MVP shipped the open-data half (identity + IRS financials) on the theory that results were permission-gated. The 2026-07-23 survey falsified that for the layer that actually holds the data: RegattaCentral appeared in 1 of 79 live-results links on row2k's 2026 directory — results live with timing providers, and the two biggest (HereNow, Time-Team's USRowing white-label) serve complete, structured, unauthenticated JSON with no stated usage restrictions. This unblocks Track D's north star: masters/juniors competitive ratings.

This spec locks the design for ingesting the timing-provider layer into the existing acquire → resolve → derive → publish rails, publishing club-linked results on org profiles, and computing ratings as strictly-gated derived metrics.

## North star

Ratings attach to *programs within boat class + age bracket* (MVP spec §North star), computed by rank-ordered-field models (Plackett-Luce family), never pairwise ELO. Everything in this spec is sequenced to feed that: results tables preserve full field order, progression graphs, and masters age handicaps; canonical event classification (boat class / age bracket / gender) is a first-class prerequisite job; a rating is one more `metric_definition` row with an eligibility rule, not new machinery.

## Decision summary

| Decision | Choice |
| --- | --- |
| Sources, order | HereNow (Breeze/OData JSON, 1,405 races 2007–2026) → Time-Team USRowing white-label (JSON API, 2020–2026 championships) → row2k directory (index only, link-don't-copy honored) → RegattaTiming (collegiate HTML) → CrewTimer (parked; spike doc only). |
| Ingestion shape | One adapter module per source on the existing rails (`IngestRun`, `RawStore` write-once R2, quarantine, staging → core). No new frameworks; `lxml` + `rapidfuzz` already in deps. |
| Core schema | New `core.regatta / regatta_event / regatta_entry / regatta_result` family + `core.provider_club`; insert-only supersede via `revision` column, latest-wins reads. Person names isolated in `core.result_person` (purgeable; FK direction guarantees results survive a purge). |
| Club → org identity | Curator-only, like EINs: pipeline generates candidates (audit_event + `club_link`/`inclusion` review tasks; Time-Team stable club UUIDs join via `external_identifier` namespace `time_team_club`); `club-curation` CLI promotes. Publish joins through verified identifiers only. |
| Provenance | New parallel contracts family (`result-ref.v1`, `org-regatta-payload.v1`). `source-ref.v1` untouched (unit stays USD\|count). Every published result value carries a ResultRef; ProvenancedValue-style rendering enforced in web. |
| Publish | Extend `publish.py` (single global snapshot pointer — a second publisher is structurally wrong). Fatal: contract validation, suppressed-name leakage, person names in search_text. Per-item: time sanity, place-without-finish → `under_review` + review_task. |
| PII | Ecosystem-norm policy, separately specified: names in race-result context only, no person pages, suppression list honored at publish, U13 events proactively redacted. |
| Ratings | `event-classify` (repo-owned mapping, concept_map pattern) then `derive-ratings` → `core.metric_value` under versioned `metric_definition` with eligibility rule; published only above gates; display flagged until backtest validates. |
| Posture | Honest UA everywhere ("crewgraphs.com/methods" contact); polite rate limits; 403 → quarantine, never silent browser-spoofing (UA override is an owner decision); attribution in `SOURCE_REGISTRY` + methods page; courtesy emails to providers once attribution is live. |

## Architecture

```
HereNow Breeze API   Time-Team /api/1   row2k index   RegattaTiming JSP
      │ (herenow.py)     │ (timeteam.py)   │ (row2k.py)   │ (regattatiming.py)
      ▼                  ▼                 ▼              ▼
  R2 raw objects (immutable, checksummed; raw/{source}/…)
      ▼                                   ▼
  staging.{herenow_*, time_team_*}    core.regatta_source_link (registry, no content)
      ▼
  core: regatta → regatta_event → regatta_entry → regatta_result
        provider_club ──(curated external_identifier)── organization
        result_person (isolated PII; suppression at publish)
      ▼  resolve-clubs (candidates) · club-curation (promotion) · event-classify
      ▼  derive-ratings → metric_value (eligibility-gated)
  publish.py: suppression + invariants → read.org_regatta_result → snapshot flip
      ▼
  /org/[slug] regatta-activity module · methods page attribution
```

### Core tables (migration 014)

- `core.regatta` — `(source, external_key, revision)` unique; provider-raw `category`, `payload_checksum` for whole-race no-op detection, `raw jsonb`, `source_record_id`, `parser_version`.
- `core.regatta_event` — event/race within a regatta; provider-raw `boat_class/age_class/gender` text + canonical columns populated later by `event-classify`; `progression jsonb` preserves Time-Team advancement rules (`rules[].target_round_id`).
- `core.regatta_entry` — bib/lane/`club_source_name` (always kept verbatim)/`provider_club_id`/`crew_label`. **No person names.**
- `core.regatta_result` — status (provider vocabulary raw), `position`, `adjusted_position`, `time_ms`, `adjusted_time_ms`, `handicap_ms`, `delta_ms`, `penalty/correction/splits jsonb`.
- `core.provider_club` — provider-side observation, `(source, external_key)` unique; external_key = Time-Team platform UUID, else normalized name. The org link lives only in curator-owned `core.external_identifier`.
- `core.result_person` — `entry_id, role, seat, person_name, raw`; explicit `REVOKE ALL FROM web_ro`; deletable without touching results.
- `core.person_suppression` — curator-only; `person_name_normalized` + optional source/club scope + reason. Enforced at publish (policy §4/§5).

All results tables: pipeline_rw SELECT+INSERT only (grants function replaced, 001/008 pattern); supersede = insert `revision+1` tree, latest-wins reads (derive.py precedent); enum extensions use 006-style type recreation in `migrate:down`.

### Read model (migration 017)

`read.org_regatta_result` — snapshot-scoped long form on the `org_financial_series` pattern: org + season + regatta dims + event dims + `crew jsonb` (post-suppression `[{role,name}]`) + `metric_key ∈ finish_time|adjusted_time|handicap|place|adjusted_place|margin` + value/unit/status/quality_state + `source_ref jsonb` (ResultRef). Optional `read.org_regatta_summary` rollup. Added to `_GC_SQL`.

### Contracts

`resultRefSchema` v1 (SourceRef-shaped; `unit: seconds|rank|margin_seconds|handicap_seconds|count`; `season`; `source {source_key, regatta_external_key, event_external_key, provider_url}`) and `orgRegattaPayloadSchema` v1 (seasons → regattas → events → entries `{crew: [{role,name}], results: [{metric_key, ref}]}`). Exported to JSON Schema alongside the v1 files; Python validates at publish and in golden tests.

### R2 layout

```
raw/herenow/catalog/{iso-instant}.json          raw/herenow/race/{raceId}/{base|flights}/{date}.json
raw/timeteam/usrowing/{slug}/{year}/index/{date}.json + /race/{uuid}/{date}.json
raw/row2k/results-index/{year}/{category}/{date}.html
raw/regattatiming/summary/{raceId}/{date}.html
```

Catalog keys are instant-stamped (catalogs mutate intra-day mid-regatta); race payloads date-stamped with refetch-window logic; same-key checksum conflicts quarantine per existing write-once semantics.

### Jobs (Typer CLI; each opens an `ops.ingest_run`; each module exposes `register(app)`)

`herenow-catalog-sync` · `herenow-race-backfill` · `herenow-load` · `timeteam-regatta-index` · `timeteam-race-sync` · `timeteam-load` · `resolve-clubs` · `club-curation` (curator) · `row2k-index-sync` · `results-gap-report` · `regattatiming-sync` · `regattatiming-load` · `event-classify` · `derive-ratings`.

GitHub Actions: `results-backfill.yml` (dispatch inputs + weekly cron offset from the IRS monthly so publish-gate `--since` windows stay disjoint), sequential steps ending in the shared `publish-gate → publish → run-report` tail.

## Source facts that bound the design (verified 2026-07-23)

1. HereNow: Breeze/OData at `newwebrole2023.azurewebsites.net/breeze/BreezeApi/` — `Races` enumerable (`$inlinecount=allpages` → 1,407 incl. 2 test rows), `GetBaseRaceData`, `GetScopedRaceFlights`; SignalR live hub; masters rows carry raw + age-handicap + adjusted times; `LastYearRaceId` chains editions; tags are messy ("Rowinf", "owing"). robots.txt allows all; no ToU anywhere. Azure host name implies churn risk → env-overridable base URL.
2. Time-Team USRowing white-label: year selector 2020–2026; `/api/1/{slug}/{year}/race` (schedule, progression rules, timing layouts w/ split locations) and `/race/{uuid}` (race_crew + round_crew: bib/lane/status vocab/adjusted pos+result/delta/penalty/correction/per-location times). Club objects carry **stable platform UUIDs + near-legal names** ("Miami Rowing and Watersports Center, Inc.") — the EIN-join surface. Legacy PHP generation (`regatta.time-team.nl`) holds older regattas; deferred (2b) pending gap data.
3. row2k: explicit policy on results pages — schools/clubs may copy their own; everyone else "*LINK TO* these results," credit row2k; robots carries `ai-train=no` content signal. Directory archives to 1997 with date/category/location + outbound provider links. Cloudflare 403s non-browser UAs.
4. RegattaTiming: sequential integer raceIds (~369=2014 Dad Vail … 644=2026 IRA); `summary.jsp?raceId=` server-rendered event sections (place/lane/club/stroke/time/margin); `staticRaceResults.jsp` for old years; Cloudflare content-signal robots; 403s non-browser UAs.
5. CrewTimer: React SPA on Firebase (`crewtimer-results.appspot.com`), `r#####` ids; data flows over Firebase channels, not inspectable REST → parked behind a spike.
6. Both open providers publish full athlete names including minors (verified down to U15) — see the PII policy for the publication stance.

## Deviations from the MVP spec

| MVP spec | This spec | Why |
| --- | --- | --- |
| "Every results source is permission-gated"; ingestion needs permission | Timing-provider layer ingested directly; aggregators (RC/row2k/Concept2) remain gated | Survey verified open unauthenticated APIs, no ToU, permissive/absent robots; providers publish on behalf of organizers |
| `regatta/event/entry/result` out of migrations | In (migration 014) | The gating condition ("a results source is secured") is met |
| Results source = "one enum value + one adapter" | Five enum values, four adapters, shared results schema | Ecosystem is provider-plural; schema is source-agnostic with provider-raw fields preserved |
| No person data beyond filings | `core.result_person` + suppression machinery | Required for ecosystem-norm display policy; isolated + purgeable by design |

## Risks

1. **Azure/API churn** (HereNow host, Time-Team `/api/1`) — env-overridable bases, R2 corpus immutable, quarantine spikes surface via publish-gate.
2. **Upstream blocks** — honest UA + slow rates; 403 quarantines; UA override is an explicit owner decision; outreach posture per Track D.
3. **Volume** — 0.5–2M core result rows plausible; publish filters to verified-linked cohort orgs; checksum no-op caps re-ingest growth; backfills chunked via workflow inputs.
4. **Vocabulary drift** (status codes, event naming, masters handicap semantics by year) — raw vocab always preserved; unknown values warn-not-quarantine; canonical mapping is versioned and review-queued, never guessed.
5. **PII exposure** — names representable only in the payload path that applies suppression; fatal publish invariants; person table purgeable; policy doc governs.
6. **PG enum irreversibility** — 006-style recreation in every down migration; CI's full rollback/reapply is the proof.

## Launch gates

Results section on a cohort profile shows only values traceable to a raw R2 object (ResultRef complete); club links publish only through curator-verified identifiers; no suppressed or search-indexed person name (invariant-tested); no rating published below its `metric_definition` eligibility rule; ratings display stays flagged off until the backtest report is in this repo.
