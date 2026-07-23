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

### Track A — Reach (make the reference useful to more of the sport)
- [ ] **Cohort expansion** `[lead triage, terra]`: promote vetted BMF discovery candidates through resolve; grow beyond the 11-org seed. Gate: identity review per org (racing identity ≠ filer in ~40% of cases).
- [ ] **Monthly cron** `[terra]`: scheduled run of the full chain (workflow is dispatch-only today); alerting on quarantine/invariant failures.
- [ ] **Compare page** `[lead defines, sol]`: side-by-side orgs on the published series + peer cohorts; spec section exists.

### Track B — Trust (the reference-site posture)
- [ ] **Methods page** `[lead]`: how concepts map to 990 lines, the missing-vs-zero rule, amendment policy, source attribution (ODbL share-alike note for GT lake).
- [ ] **`raw_url` in SourceRefs** `[luna]`: link each fact to its publicly addressable filing object; currently null.
- [ ] **Corrections flow + admin UI** `[sol]`, then **CF Access policy on `/admin/*`** `[owner]` — the one remaining SETUP item.

### Track C — Platform hygiene
- [ ] **Widen `read.org_directory`** `[terra]`: directory entries are assembled from payload headers at request time; move city/state/org_type/program_mix into published columns.
- [ ] **KV caching + publish-hook** `[terra]`: serve the directory blob from KV, bust on snapshot flip.
- [ ] **SEO/OG + a11y/perf hardening pass** `[luna, lead review]`.
- [ ] **Fixture enrichment** `[luna]`: people/relationships demo coverage for the new profile sections.

### Track D — North star (permission-gated, owner-led)
- [ ] **RegattaCentral / Concept2 / row2k outreach** `[owner]`: open permission conversations from the live-site position. Not a launch gate; ratings work (rank-ordered-field models per boat class + age bracket) starts only when a results source is secured.

## Verification bar (unchanged)

Every published figure traceable to an exact source path; publish blocked by contract validation + identity invariants; no metric without a versioned definition; comparisons aligned on TaxYr.
