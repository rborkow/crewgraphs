# CrewGraphs Results Ingestion Plan — waves, fan-out, reviews

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Every delegated task lands as an uncommitted, PR-shaped diff with tests; the lead inspects diff + test output before committing. Workers never run git commit. Wave-1 workers run in isolated worktrees and must not touch the frozen shared files (below).

**Spec:** `docs/superpowers/specs/2026-07-23-results-ingestion-design.md` · **PII policy:** `docs/superpowers/specs/2026-07-23-athlete-pii-policy.md` · **Research:** `docs/superpowers/research/2026-07-23-results-timing-providers.md` · **Parent plan:** `2026-07-22-crewgraphs-post-mvp.md` (Track D)

**Delegation legend:** `[lead]` Fable/Claude · `[terra]`/`[luna]`/`[sol]` Codex tiers per global routing · `[owner]` human-only.

**Coordination rules (the fan-out contract):**
- Migration numbers pre-assigned: `014_results_core` (Wave 0) · `015_row2k_registry` (W1c) · `016_regattatiming` (W1d) · `017_read_regatta` (Wave 2). W1a/W1b ship no migrations (their staging is in 014).
- Frozen during Wave 1: `pipeline/src/crewgraphs/jobs/publish.py`, `packages/contracts/**`, `pipeline/src/crewgraphs/__main__.py`. Each adapter exposes `register(app)` in its own module; the lead wires one-line registrations at merge.
- Nothing merges without its review pass. Reviews use distinct lenses, cross-model where blast radius is high.

---

## Wave 0 — foundations `[lead]`

- [x] Spec + PII policy + this plan; Track D pointer in the parent plan.
- [x] Migration `014_results_core.sql`: source_type/identifier_namespace enum extensions (006-style downs), core regatta family, `provider_club`, `result_person` (web_ro revoked), `person_suppression` (curator-only), herenow/timeteam staging, grants-function replacement (001/008 pattern). Note: `revision` lives on `core.regatta` only — a re-load inserts a fresh child tree scoped by FK; children carry no revision bookkeeping.
- [x] Contracts: `resultRefSchema` + `orgRegattaPayloadSchema` v1, schema export, `test_contracts.py` golden fixtures (9 pass).
- [x] Verify (2026-07-23, ephemeral PG16+PG18): dbmate up + full 14-step rollback/reapply; 9/9 role-grant probes (web_ro denied on `result_person`/`person_suppression`; pipeline_rw INSERT-only on `regatta`, read-only on suppression, no DELETE on `result_person`; curator purge works); `db/schema.sql` regenerated in dbmate format.

## Wave 1 — adapter fan-out (parallel worktrees)

- [ ] **W1a HereNow** `[terra]`: `jobs/herenow.py` — `herenow-catalog-sync`, `herenow-race-backfill` (refetch window, sleep), `herenow-load` (checksum no-op → revision trees; masters raw/handicap/adjusted mapping); test-race skip-set; fixtures + tests; `HERENOW_BASE_URL` override.
- [ ] **W1b Time-Team** `[terra]`: `jobs/timeteam.py` — `timeteam-regatta-index` (`__NEXT_DATA__` parse, `--slugs` fallback), `timeteam-race-sync`, `timeteam-load` (club UUIDs → provider_club; stroke → result_person; progression + splits jsonb); fixtures + tests.
- [ ] **W1c row2k index** `[terra/luna]`: migration `015_row2k_registry.sql` (`core.regatta_source_link` — facts + outbound URLs only, test asserts no content columns), `jobs/row2k.py` (`row2k-index-sync`, honest UA, 403 → `row2k_blocked` quarantine), `results-gap-report`.
- [ ] **W1d RegattaTiming** `[terra]`: migration `016_regattatiming.sql`, `jobs/regattatiming.py` (`regattatiming-sync` id-range + probe-forward, `regattatiming-load`, lxml parse with column-count shape check → quarantine on drift).
- [ ] **USER_AGENT generalization** (one line in `__main__.py`, lead applies at first merge): "public rowing data pipeline; crewgraphs.com/methods".
- [ ] `.github/workflows/results-backfill.yml` `[lead]` at merge: dispatch inputs + weekly cron (offset from IRS monthly), sequential steps → shared publish-gate/publish tail.

### Review pass R1 (per branch, before merge)
- [ ] Lenses: correctness vs raw fixtures · idempotency/quarantine/revision behavior · scraping posture (UA, rates, 403) · PII containment (names only in `result_person`). `[sol]` on the hardest branch, `/codex:adversarial-review` cross-model on the rest; lead inspects diff + test output.
- [ ] Live smokes post-merge: 2–3 HereNow races (one masters), one Time-Team regional-champs year; `run-report` clean.

## Wave 2 — convergence (serial: shared files unfreeze)

- [ ] **Phase 3 identity join** `[terra]`: `jobs/resolve_clubs.py` (exact UUID tier → near-legal-name similarity ≥0.85 auto-candidate / 0.6–0.85 review / BMF EIN-boost `inclusion` tasks; HereNow frequency gate ≥3 regattas); `club-curation --csv seed/club_links.csv` curator promotion; match-rate stats (expect Time-Team ≥60% auto, HereNow 20–30%).
- [ ] Seed `seed/club_links.csv` for the published cohort `[lead triage, owner sign-off]`.
- [ ] **Phase 4 publish** `[sol]`: migration `017_read_regatta.sql` (+`_GC_SQL`); `publish.py` — regatta source rows through verified links only, suppression + U13 assembly, ResultRef/payload validation, per-item `under_review` downgrades, fatal name-leakage + search_text invariants, `SOURCE_REGISTRY` entries.
- [ ] **Phase 4 web** `[lead]`: `regatta-activity.tsx` replaces the placeholder (season-grouped, provenanced, provider link-outs, mm:ss.t); methods page results section + PII policy plain-language + takedown contact.

### Review pass R2 (on the convergence diff)
- [ ] PII enforcement (suppression, search leakage, U13) `[sol]` · schema/grants/GC `[terra]` · product/copy/a11y `[lead or opus]`. Cross-model mandatory.
- [ ] Full chain on cohort: results render on a live profile; rollback + GC verified.

## Wave 3 — ratings (3a may start parallel to Wave 2)

- [ ] **3a event-classify** — mapping candidates `[luna]`, curation `[lead]/[owner]`: provider event codes → canonical boat_class/age_bracket/gender (concept_map pattern; unmapped → review queue, never guessed); coverage stats.
- [ ] **3b derive-ratings** `[sol]`: Plackett-Luce-family strength per org × boat_class × age_bracket per season → `core.metric_value` under new `metric_definition` (`rating_rof` v1, eligibility: ≥N ranked fields across ≥M regattas); `read.org_rating_series` publish above gates only.
- [ ] **R3**: adversarial review of eligibility gates `[sol]` + backtest report (held-out later-season finish-order prediction, rank correlation) checked into `docs/superpowers/research/` before the display flag flips `[lead]`.

## Anytime

- [ ] Phase 7 CrewTimer spike doc under `spike/` `[luna]` (Firebase REST readability, id-space enumeration, unpark criteria).
- [ ] Courtesy emails to info@time-team.nl and HereNow once attribution is live `[owner]`.
- [ ] Sub-phase 2b (legacy Time-Team PHP scraper) — decide from `results-gap-report` numbers.

## Verification bar

CI green incl. full migration rollback/reapply at every wave · every published result value traceable to a raw R2 object via a complete ResultRef · club links publish only through curator-verified identifiers · zero suppressed or search-indexed person names (invariant-tested) · no rating below its published eligibility rule · gap-report coverage sane vs the survey's market-share table.
