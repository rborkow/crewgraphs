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

## Wave 1 — adapter fan-out (parallel worktrees) — MERGED 2026-07-23

- [x] **W1a HereNow** (terra, commit fbfe7fe): all three commands; real Cromwell Cup fixtures; canonical checksum resolves Breeze `$ref`/strips `$id` (R1 blocker); provider-only classification; namespaced club keys; contact stripping.
- [x] **W1b Time-Team** (terra, 4754a37): index via server-rendered anchors (`?year=` verified live; `__NEXT_DATA__` was a dead end); real 1x + 8+ fixtures (payload carries stroke_fullname only — full rosters are a separate uncalled endpoint); volatile-timestamp canonicalization (R1 blocker); PHP `[]`-for-`{}` empties tolerated.
- [x] **W1c row2k index** (terra, 9a6a0f8): migration 015 w/ `NULLS NOT DISTINCT` dedupe; parser validated on the real 2025 directory (883/883 dated+categorized, 29 archive years from the `<select>` — not anchors); revision-safe gap report.
- [x] **W1d RegattaTiming** (terra, 77f6fd6): migration 016; strict six-column real-markup parser (browser-captured 2025 IRA fixture; Cloudflare fronts the site — challenge/403/429/503 all quarantine-and-stop); `data-org-id` club keys; PII blocker fixed (entry raw is club-only).
- [x] **USER_AGENT generalization** (landed with the runtime extraction, 9305288).
- [x] `.github/workflows/results-backfill.yml` (integration commit): dispatch inputs + weekly Monday cron offset from the IRS monthly.

### Review pass R1 — done (4 × opus adversarial reviewers; cross-model vs the GPT builders)
- [x] All four lenses per branch; 2 blockers found and fixed (checksum instability from volatile serialization artifacts in both JSON adapters; stroke-name PII leak into entry raw in W1d); ~12 should-fixes landed via Codex fix rounds; lead verified every branch with full pytest (119 total post-merge) + ephemeral-Postgres migration checks (PG16 rollback/reapply, PG18 dump parity).
- [ ] Live smokes post-merge: 2–3 HereNow races (one masters), one Time-Team regional-champs year; `run-report` clean. `[lead]` — needs DB/R2 secrets, run via workflow dispatch or locally with .env.

## Wave 2 — convergence — MERGED 2026-07-23

- [x] **Phase 3 identity join** (terra, 378c0ea): `resolve-clubs` (exact-link skip; Time-Team ≥0.85 auto-candidate with any-two-≥0.85 ambiguity guard + durable rejects; 0.6–0.85 review; BMF EIN-boost inclusion tasks; revision-safe ≥3-regatta frequency gate) + `club-curation` curator promotion + `seed/club_links.csv` scaffold.
- [ ] Seed `seed/club_links.csv` from real resolve-clubs output `[lead triage, owner sign-off]` — needs a live run (secrets).
- [x] **Phase 4 publish** (sol, 9837584): migration 017 (`read.org_regatta_result` incl. `entry_external_key`), curated-links-only join with a single-org ambiguity guard, NFKC/token-set suppression + broadened U13 redaction (incl. `crew_label` nulling), fatal invariants (suppressed-name scan over crew/crew_label/club_display_name, person-names-in-search_text, duplicates, assembly errors), sanity downgrades, six ResultRef metrics, SOURCE_REGISTRY, GC.
- [x] **Phase 4 web** (lead, 48a0967): `RegattaActivity` + `ResultValue` (ResultRef-required twin of ProvenancedValue) + pure mappers/formatters with tests; attribution/takedown line inline (methods page itself remains Track B).

### Review pass R2 — done
- [x] Dual review of the publish diff: opus PII lens (3 redaction bypasses found: unguarded `crew_label`, U13 regex false negatives, unicode-asymmetric suppression) + terra technical lens (multi-org alias-join blocker, entry-key collision, `assembly_errors` KeyError) — all findings landed in one sol fix round; identity branch reviewed by opus (frequency-gate revision overcount + non-durable rejects, fixed). 159 pipeline + 88 web tests green; migrations 015–017 each verified up/rollback/reapply on ephemeral PG16 with grant probes.
- [ ] Full chain on cohort against the live DB: curate first links, dispatch results-backfill, verify a profile renders results + rollback/GC `[lead/owner]` — needs secrets.

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
