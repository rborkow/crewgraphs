# CrewGraphs Post-MVP Plan — where we are, what's next

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Every delegated task lands as an uncommitted, PR-shaped diff with tests; the lead inspects diff + test output before committing. Workers never run git commit.

**Spec:** `docs/superpowers/specs/2026-07-21-crewgraphs-mvp-design.md` · **Predecessor:** `2026-07-21-crewgraphs-phase0.md` (Phases 0–1, complete)

**Delegation legend:** `[lead]` Fable/Claude · `[terra]`/`[luna]`/`[sol]` Codex tiers per global routing · `[owner]` human-only (credentials, judgment, sign-off).

---

## Shipped (as of 2026-07-22)

The MVP loop is closed and in production: **crewgraphs.com serves real IRS data end-to-end.**

### Pipeline (Phase 2 — complete)
- Seven acquisition jobs live on GitHub Actions (`irs-backfill.yml`, manual dispatch): BMF → 990-N → e-file index → fetch (GivingTuesday lake) → parse → ProPublica bootstrap → cross-check.
- Cross-check quality bar: 172/172 anchor values match ProPublica exactly (8 expected EZ nulls, 60 expected lag gaps).
- resolve → derive → publish complete the chain: contract-validated payloads, atomic snapshot flip, three-snapshot retention, rollback job.
- Full chain runs green in ~14 minutes; run stats + quarantine on every job.

### Web (Phase 3 — complete)
- Directory with alias search/filters/URL state; `/org/[slug]` profiles with provenanced snapshot facts, trend charts wired chart-point → SourceDrawer, 990-N explainer, slug 308 redirects.
- Design language "regatta program, modern instrument"; every rendered figure requires a full SourceRef (provenance-less numbers are unrepresentable).
- OpenNext on Cloudflare Workers, reads `read.*` over Hyperdrive (postgres.js), custom domains bound.

### Profile detail layer (2026-07-22 — complete)
- **Financial composition:** "Where the money comes from / goes" tables on every 990/990-EZ profile — revenue lines (contributions, program service, dues, investment, fundraising net, other) and expense lines (functional split + notable line items), each cell a SourceDrawer with share-of-total, per-form caveats footnoted.
- **Multi-year people:** the People section publishes every filed year, not just the latest.
- **Part VII deep capture:** extractor now takes other/related-org compensation, average hours, and the five position checkboxes; migration 013 added `person_role.avg_hours_week`; publish collapses INSERT-only superseding captures to the newest per (filing, person, title). Live: officer hours + role labels on profiles.
- **Coverage repair:** index year 2022 restored to the dispatch defaults (processing-year scatter had left FY2021 gaps — Vesper and Marin both filled).
- **Rollout tooling:** `efile-parse --reparse` + workflow boolean input is the standing path for extractor changes: migrate → dispatch with `reparse=true` → publish flips enriched data.

### Cohort
- 11 real organizations published (OARS correctly candidate-excluded); 687 BMF discovery candidates and 1,234 990-N rows staged for expansion.

---

## Next steps

Ordered roughly by product value; independent tracks can run in parallel.

### Track A — Reach (make the reference useful to more of the sport) — COMPLETE 2026-07-23
- [x] **Cohort expansion batch 1** `[lead triage, terra]`: 69 orgs published (was 11). 675-candidate triage; the ranked Tier-2 pool of 268 clean rowing orgs for batch 2 lives in `docs/superpowers/research/2026-07-22-cohort-triage.md`.
- [x] **Monthly cron** `[terra]`: 5th of the month 09:00 UTC + publish gate (quarantined chains never publish; filer arithmetic errors downgrade to under_review).
- [x] **Compare page** `[sol]`: 2–4 orgs aligned on TaxYr, provenanced cells, CSV export.

**Batch-2 prerequisites (before promoting the Tier-2 pool):** derive the EIN watchlist from the DB (the 70-EIN dispatch input is already unwieldy), resolve provisional `org_type` on the 58 batch-1 promotions.

### Track B — Trust (the reference-site posture) — COMPLETE & LIVE 2026-07-23
- [x] **Methods page** `[lead]`: shipped (`be224ca`) — /methods (sources & ODbL/PP/NODC attribution from read.source_registry_public, 24-concept table drift-guarded against the pipeline YAML, missing-vs-zero, quality states, TaxYr alignment, amendments, people rule) + /methods/[metricKey] per-metric pages from read.metric_catalog. Fixed the standing header/footer 404.
- [x] **`raw_url` in SourceRefs** `[luna]`: shipped (`a240bd0`) — XML-backed refs link the GT-lake object; 990-N/BMF/multi-input-metric refs stay null. Takes effect on next publish dispatch.
- [x] **Corrections flow + admin UI** `[sol]`: shipped (`b514f35`) — migration 014 grants (web_ro INSERT-only on app.correction_submission; admin_ro read role), POST /api/corrections + /corrections/new (honeypot, snapshot-scoped slug resolution), read-only /admin{,/review,/corrections} gated on Cf-Access-Jwt-Assertion presence + ADMIN_DATABASE_URL. Status mutations stay in the audited curation CLI (follow-up: `curation corrections resolve` subcommand; in-app Access JWT validation).
- [x] **Owner activation** `[owner]` done 2026-07-23: admin_ro + migration 014 + ADMIN_DATABASE_URL + CF Access on /admin/* (SETUP now fully complete) + deploy + publish dispatch. Verified live: snapshot ee506961 carries raw_url on 9,147/9,209 series rows (62 nulls = revenue_cagr, multi-filing window, null by design); profile drawers link GT-lake objects (spot-checked 200). Ops lesson recorded: `gh workflow run` executes origin/main — push before dispatching (first activation run published from stale code).

### Track C — Platform hygiene
- [ ] **Widen `read.org_directory`** `[terra]`: directory entries are assembled from payload headers at request time; move city/state/org_type/program_mix into published columns.
- [ ] **KV caching + publish-hook** `[terra]`: serve the directory blob from KV, bust on snapshot flip.
- [ ] **SEO/OG + a11y/perf hardening pass** `[luna, lead review]`.
- [ ] **Fixture enrichment** `[luna]`: people/relationships demo coverage for the new profile sections.

### Track D — North star (permission-gated, owner-led)
- [ ] **RegattaCentral / Concept2 / row2k outreach** `[owner]`: open permission conversations from the live-site position. Not a launch gate; ratings work (rank-ordered-field models per boat class + age bracket) starts only when a results source is secured.

## Verification bar (unchanged)

Every published figure traceable to an exact source path; publish blocked by contract validation + identity invariants; no metric without a versioned definition; comparisons aligned on TaxYr.
