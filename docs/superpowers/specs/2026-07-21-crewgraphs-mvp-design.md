# CrewGraphs MVP Design

**Date:** 2026-07-21
**Status:** Approved
**Source PRD:** "Rowing FanGraphs" PRD v1.0 (2026-07-21) — this spec supersedes it where they differ.

## Problem

Rowing has rich public data — regatta results, blade references, governing bodies, nonprofit filings — but it is fragmented, and no product connects a club's identity, activity, and financial context in one trusted place. The PRD defines the product; this spec locks the decisions needed to build it as a solo-owner + AI-agent project rather than the PRD's assumed 2–3 person team.

**Name:** CrewGraphs (crewgraphs.com, owned, registrar/DNS on Cloudflare). "Rowing FanGraphs" appears nowhere public.

## North star

**Masters/juniors-level competitive ratings** are the long-term destination. Every results source is permission-gated (RegattaCentral, Concept2, row2k), so the MVP ships the fully-open-data half first: a canonical identity + IRS financial reference. Sequencing rationale: permission conversations go better with a live, trusted site in hand.

Ratings notes recorded now so MVP schema thinking doesn't foreclose them:
- Rating models for multi-boat races are rank-ordered-field models (Plackett-Luce / TrueSkill family), not pairwise ELO, and ratings attach to *programs within boat class + age bracket*, not clubs.
- MVP prerequisites already in scope: the identity graph (attributing entries to the right program is an identity problem first), versioned metrics with eligibility gating (a rating is a strictly-gated derived metric), and source-agnostic ingestion.
- `regatta/event/entry/result` tables stay OUT of MVP migrations. The `external_identifier` namespace enum reserves `regattacentral_org`; adding a results source later is one enum value + one adapter.

## Decision summary

| Decision | Choice |
| --- | --- |
| Scope | IRS-first: EO BMF + Form 990/990-EZ XML + 990-N for 50–150 hand-curated US rowing orgs, ~5 fiscal years. No RegattaCentral/OarSpotter dependency at launch. |
| Web stack | Next.js App Router via `@opennextjs/cloudflare` on Workers; Tailwind 4 + shadcn/ui; TanStack Query; Vitest. Kysely + kysely-codegen over `pg` via Hyperdrive → Neon Postgres. |
| Data stack | Python (`pipeline/`, uv + Typer CLI) jobs on GitHub Actions; Cloudflare R2 for immutable raw payloads; plain-SQL migrations via dbmate (shared by TS and Python). |
| XML fetch | GivingTuesday 990 data lake (anonymous S3, per-object fetch, ODbL) primary; IRS monthly batch zips authoritative fallback. irs.gov has **no** per-filing endpoint. |
| Parsing | Repo-owned 24-concept YAML map (seeded from the NODC master concordance as *reference data*, hand-patched against IRS XSDs) driving a small lxml extractor. Not a general 990 parser. IRSx is dormant (schema support ends 2018) — prior art only. |
| Validation | ProPublica Nonprofit Explorer API v2 (keyless) for cohort discovery, EIN confirmation, and a continuous cross-check: 6 anchor concepts must match ProPublica's extraction exactly. GT datamarts as second cross-check. PP data is never published as canonical. |
| Identity | Deterministic: hand-curated `seed/cohort.csv` → verified EIN links → auto-attach + audit. Guards: name-similarity sanity check blocks suspicious attaches; hard conflict rule (one EIN, one org, absent an explicit relationship). Scoring bands exist only in the monthly candidate-discovery sweep. |
| Admin | No console suite. Audit-grade data model (review_task, audit_event, reversible merges) + audited `curation` CLI + two thin pages behind Cloudflare Access. |
| Editorial | No composite club score. Versioned metric definitions with eligibility rules and quality states are first-class product content. Provenance drawer on every displayed number. |

## Architecture

```
GivingTuesday lake / IRS bulk / ProPublica
        │  (Python jobs, GitHub Actions cron)
        ▼
  R2 raw objects (immutable, checksummed)
        ▼
  Neon Postgres: staging → core (canonical graph + facts) → read (snapshot-versioned read models)
        │                                    ▲
        │  publish job: invariants → build snapshot → flip pointer → POST /api/internal/publish-hook
        ▼                                    │
  Workers app (OpenNext Next.js) ── Hyperdrive ──┘
        │  KV: directory blob + publish pointer; edge HTML cache
        ▼
  crewgraphs.com
```

### Database schemas (= permission boundaries)

- `core` — canonical graph + facts. Roles: `pipeline_rw` (facts only — **cannot** UPDATE identity tables), `curator` (identity writes, only via the audited CLI).
- `staging` — per-run parsed source data.
- `ops` — ingest runs, quarantine, publish snapshots.
- `read` — published read models. `web_ro` can see **only** this schema.
- `app` — web-writable (correction submissions). `admin_v` — read-only views over core review tables for admin pages.

### Core entities (migration 001–00x)

organization (status: candidate|included|excluded|merged; non-destructive merges via `merged_into_id`) · external_identifier (namespace enum incl. reserved `regattacentral_org`; partial unique on verified+active) · organization_alias (normalized generated column) · organization_relationship (program_of, fiscally_sponsored_by, successor_of, supports, boosters_for, shares_boathouse_with) · source_record (immutable, checksummed, R2 URI) · ein_observation (append-only BMF history) · epostcard_observation (990-N presence; never synthesized into financials) · filing (amendment precedence → `is_authoritative`; superseded rows kept) · financial_fact (exact XPath + `normalization_version`; re-parse = new version rows) · concept_definition · person_role (filing-scoped, org-level only — no cross-org person graph) · metric_definition / metric_value (versioned; eligibility jsonb) · review_task · audit_event (every identity mutation; merge events store the full inverse so `unmerge` is a real command).

### The 24-concept financial catalog

total_revenue · total_expenses · revenue_less_expenses · contributions_grants · program_service_revenue · membership_dues · investment_income · fundraising_events_gross · fundraising_events_net · other_revenue · grants_paid · salaries_benefits_total · officer_compensation · professional_fundraising_fees · occupancy · program_service_expense¹ · management_general_expense¹ · fundraising_expense¹ · total_assets_eoy · total_liabilities_eoy · net_assets_eoy · cash_savings_eoy² · land_buildings_equipment_net · employee_count¹

¹ 990-only (functional splits / Part I line 5). ² partial on 990-EZ (L22 mixes investments). EZ-missing concepts render **"unavailable — not on 990-EZ"**, never zero.

Derived metrics v1: operating_margin, revenue_cagr (≥3 observations), contribution_dependency, program_service_share, compensation_intensity, membership_dues_share. Quality states: verified | derived | partial | unavailable | under_review (partial and under_review are never ranking-eligible).

### Pipeline jobs (Typer CLI, each opens an `ops.ingest_run`)

`bmf_sync` · `efile_index_sync` (cross-checks IRS index vs GT/PP indexes — IRS indices miss filings) · `efile_fetch` (GT lake per-object; IRS zips fallback) · `efile_parse` (unknown tag/version → quarantine, never dropped) · `epostcard_sync` · `propublica_bootstrap` · `resolve` · `derive` · `cross_check` · `publish` (invariant checks → snapshot build → atomic pointer flip → web publish-hook) · `rollback` · `backfill` · `curation` · `run_report`.

GitHub Actions: `irs-monthly.yml` (cron; publish gated on zero hard quarantines), `backfill.yml`, `publish-only.yml`, `rollback.yml`, plus per-package CI.

R2 bucket `crewgraphs-raw`: `raw/irs/{bmf,efile-index,efile-xml,990n}/…`, `raw/propublica/org/{ein}/…`, `manifests/runs/{run_id}.json`. Objects are write-once; a checksum conflict is a quarantine event.

### Read-model contract (web ⇄ data)

Atomic publish: every `read.*` row carries `snapshot_id`; single-row `read.published_snapshot` flips transactionally; last 3 snapshots retained; rollback = one UPDATE + re-fire publish-hook.

Tables: `org_directory` (coverage_state: 990|990ez|990n_only|none; aliases jsonb; tsvector populated for the post-MVP growth path — MVP search ships the whole directory blob to the client) · `org_profile` (jsonb header/snapshot/people + `payload_schema_version`) · `org_financial_series` (tidy/long: key, version, fy_end, value, quality_state, is_amended, source_ref jsonb — concepts and derived metrics share the table, namespaced keys) · `org_filing_coverage` (drives missing-vs-zero and 990-N states deterministically) · `org_peer_cohort` (reason labels) · `metric_catalog` · `source_registry_public` · `org_slug_history` (301s; slugs never reused).

**SourceRef** (zod schema in `packages/contracts`, exported as JSON Schema, validated by web CI *and* Python golden tests) is the provenance atom: value, unit, period, quality_state, source {source_key, form_type, filing_id, source_path, raw_url}, retrieved_at, parser_version, metric {key, version}. The `ProvenancedValue` React component is the only sanctioned way to render a metric, and its props **require** a full SourceRef — provenance-less numbers are unrepresentable in the type system. This is how the PRD's "100% of displayed facts carry source metadata" gate is enforced against agent-written code.

### Web surface

Routes: `/` (directory-first home, client-side alias-aware search over a KV-served index blob) · `/org/[slug]` (identity header → snapshot → trends with chart|table toggle → "Regatta activity — coming soon" module slot → people-from-filings → sources & corrections) · `/compare?orgs=&fy=` (latest-common-FY default, per-cell quality chips, CSV export) · `/methods[/metricKey]` (MDX + metric catalog) · `/about` · `/admin{,/review,/corrections}` behind Cloudflare Access · APIs: `POST /api/corrections`, `GET /api/compare`, `POST /api/internal/publish-hook` (bearer).

Charts: hand-rolled SVG kit (`packages/charts`, d3-scale/d3-shape only): server-rendered in RSC, every data point a focusable `<button>` opening the SourceDrawer, `SeriesTable` twin for every chart. Empty/partial states are core UX built from fixtures day one: 990-N-only panel, missing-year gaps never interpolated, amended markers, under_review suppressed in compare, unavailable ≠ 0 ≠ blank.

Caching: edge HTML `s-maxage=3600, stale-while-revalidate=86400`; KV directory blob at immutable `directory:{snapshot_id}` keys behind a `publish:current` pointer; Hyperdrive for the rest. Performance budget: ≤2 queries per public page, LCP < 2.5s p75 mobile (measured at scaffold time and again at hardening).

## Source facts that bound the design (verified 2026-07-21)

1. irs.gov serves XMLs only inside 100–400MB monthly batch zips; yearly `index_{YYYY}.csv` maps EIN→OBJECT_ID→batch. GT data lake (`s3://gt990datalake-rawdata`, anonymous) allows per-object fetch — primary path; ODbL attribution + share-alike applies to derivative databases.
2. The 2021–2022 XML corpus is thin (IRS pulled ~400k filings in July 2022, never fully restored). Filing lag is 6–18 months post-FYE. "Five comparable years" is aspiration, not guarantee — coverage states carry the story.
3. ProPublica API v2: keyless; terms permit a free attributed reference product that adds analysis; no wholesale republication; raw-XML endpoint is bot-blocked and off-limits to scripts.
4. NODC concordance: alive (v1.0.0, 2025) but license metadata is ambiguous — consumed as reference data to derive our own map, with an acknowledgment on the methods page.
5. 990-N orgs never appear in the XML corpus; small clubs will be 990-N-only forever. That's a designed-for state, not a gap.
6. Activity proxies for later: Concept2 (official API, needs written permission — strongest juniors/masters signal), USRowing directory (manual cross-reference OK), row2k/HereNow/RegattaCentral results (link-outs fine; ingestion needs permission).

## Deviations from the PRD

| PRD | This spec | Why |
| --- | --- | --- |
| RegattaCentral gates phase zero | Deferred entirely; schema reserves its namespace | Partnership negotiation off the solo critical path |
| From-scratch parser families + broad golden files | 24-concept YAML map + ~200-line extractor + PP/GT cross-checks | Bounded fact set; ecosystem does the schema-drift mapping |
| Admin console suite, dual review | Audited `curation` CLI + 2 thin CF-Access pages | Audit-grade model without team ceremony |
| §13 scoring bands as the resolver | Deterministic EIN attach + guards; bands live in discovery sweep only | Hand-curated cohort makes fuzzy matching the exception |
| OarSpotter blade workflow in MVP | Dropped; `blade_state` field + neutral placeholder | Licensing risk, zero launch value; claim-your-club solves it later |
| "Rowing FanGraphs" | CrewGraphs | Trademark; domain owned |

## Risks

1. 2021–22 corpus hole vs the "≥3 observations for 90% of cohort" launch gate — spike measures; pad cohort.
2. Racing identity ≠ legal filer (boosters, school programs, foundations) — modeled via relationships; constrains which archetypes are financially comparable; profile copy must say whose money is shown.
3. OpenNext bundle / Workers cold start vs LCP target — measured at scaffold; escape hatch is static-rendering profile payloads to KV at publish.
4. Contract churn on jsonb payloads — JSON Schema validated in both CIs + payload_schema_version + fixture cohort as executable spec.
5. Audit-boundary discipline with agent-written code — DB role separation is the backstop (pipeline role physically cannot write identity tables).

## Spike outcomes (2026-07-21) — validated revisions

The phase-zero spike (10 real clubs, 28 XMLs, 14 return_versions 2015–2025; see `spike/report.md`) returned **GO** on the concept-map approach: zero xpath failures, and 118/118 anchor values matched ProPublica to the dollar wherever both sides carry a value. Revisions folded into the build:

1. **XML source of record = GT lake keyed by object_id, with an explicit staleness policy.** The lake lags the IRS by months (2026-processed object IDs 404); the classic `s3://irs-form-990` bucket is dead. Add a backfill poller for lagging objects; IRS batch zips remain the only fallback for the freshest filings.
2. **Build a persistent `EIN → object_id[]` lookup once** (GT all-years index or one-time SQLite ingest of the yearly CSVs) — IRS index CSVs are 50–90MB each, ignore HTTP Range, and scatter one org across processing years. Filter out 990-T at ingest. Join on **EIN only** — the same EIN carries different names across ProPublica vs the IRS index.
3. **Racing identity ≠ legal filer is the norm** (4 of 10 in the spike: for-profit entanglement, c4/c3 sibling arms, boosters, a 990-N-only university foundation). The relationship layer is core plumbing; expect **~20% of known clubs to be 990-N or dormant** — a designed state, not an error.
4. **Comparison alignment is on IRS TaxYr with `fye_month` surfaced** — TaxYr ≠ FYE calendar year for June/October filers (3 of 10 in the spike). "Latest common year" = newest TaxYr all compared orgs have filed.
5. **Officer compensation needs a display rule, not cleaning:** 90% of Part VII rows are $0 volunteer directors. Publish only compensated individuals plus an aggregate volunteer count — less noise, less PII.
6. **The modern 990 schema is stable** (element names constant since 2013) — the concept map needs a 990 vs 990-EZ fork but no per-version xpath forks. Concordance CSV is Windows-1252, not UTF-8.
7. **Amendment precedence is wired but unvalidated** — no amended XML appeared in the spike set; ProPublica "R"-suffix form types identify orgs with amendment chains for the next test batch.

## Launch gates (inherited from PRD §5, unchanged)

≥95% of cohort has reviewed canonical identity; ≥90% has ≥3 filing observations or an explicit 990-N state; 100% of displayed facts carry source/period/version metadata; no ranking inclusion below a metric's published eligibility rule.
