# CrewGraphs Phase 0–1 Implementation Plan

> **Status (2026-07-22): COMPLETE.** Phases 0–1 passed their gates; Phases 2–3 shipped through this plan's successor work and crewgraphs.com now serves the live read model. Current state and next steps: `docs/superpowers/plans/2026-07-22-crewgraphs-post-mvp.md`.

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Every delegated task lands as an uncommitted, PR-shaped diff with tests; the lead inspects diff + test output before committing. Workers never run git commit.

**Goal:** Stand up the CrewGraphs monorepo, validate the IRS data approach end-to-end on 10 real clubs, and lay the data foundation (migrations + contracts + fixtures) that lets the data and web tracks run in parallel from Phase 2 onward.

**Spec:** `docs/superpowers/specs/2026-07-21-crewgraphs-mvp-design.md`

**Delegation legend:** `[lead]` Fable/Claude · `[terra]`/`[luna]`/`[sol]` Codex tiers per global routing · `[owner]` human-only (credentials, judgment, sign-off).

---

## Phase 0 — Docs, scaffold, spike (parallel tracks)

### Task 0a: Design docs `[lead]` — DONE
- [x] Write MVP design spec (`docs/superpowers/specs/2026-07-21-crewgraphs-mvp-design.md`)
- [x] Write this plan
- [x] Commit docs

### Task 0b: Repo scaffold `[terra]` — DONE
- [x] Bun-workspaces monorepo: `apps/web` (Next.js App Router + `@opennextjs/cloudflare`, Tailwind 4, shadcn/ui, TanStack Query, Vitest), `packages/contracts` (SourceRef zod schema + JSON Schema export + tests), `packages/charts` (stub), `pipeline/` (uv + Typer CLI skeleton with all 14 job subcommands stubbed, pytest smoke test), `db/` (dbmate layout), `seed/cohort.csv` header, CI workflows (ci-web, ci-ingest, ci-db), `SETUP.md` (owner checklist)
- [x] Acceptance: `bun install` + `bun run typecheck` + vitest (web, contracts) + `uv run pytest` + `python -m crewgraphs --help` (14 subcommands) + OpenNext build all pass locally
- [x] Lead review of diff + acceptance output; commit
  - Lead fixes required: OpenNext build recursion (build script self-invoked → fork bomb; split into `build`/`build:worker`), TypeScript pinned to ^5 (Next 16 rejects the TS7 native preview), bun `--filter` replaced with `bun run --cwd`, `@vitejs/plugin-react` + `@/` alias added to vitest config, `@types/node` + explicit `types` for contracts.

### Task 0c: IRS data spike `[opus worker + lead triage]` — DONE, verdict GO
- [x] Confirm legal entity + EIN for 10 cohort orgs via ProPublica (findings: Saugatuck nonprofit dormant/for-profit entangled → Marin substituted; Lincoln Park c4/c3 sibling arms; Husky Rowing Foundation 990-N-only)
- [x] Locate + fetch 28 XMLs across 10 EINs, 14 distinct return_versions (2015v2.0–2025v4.0)
- [x] 24-concept extractor: zero xpath failures; resolved/absent($0)/not_on_form distinguished
- [x] Cross-check: 118/118 comparable anchor values match ProPublica to the dollar; all divergences are ProPublica EZ-NULLs or its 1–2yr lag
- [x] `spike/report.md` with the 10 answers + GO
- [x] Lead review: findings folded into spec ("Spike outcomes" section); spike committed

### Task 0d: Owner setup `[owner]` — DONE except CF Access
- [x] Neon project; roles `pipeline_rw`, `curator`, `web_ro`; note DATABASE_URL
- [x] R2 bucket `crewgraphs-raw` + API token
- [x] GitHub repo + secrets (NEON_DATABASE_URL, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)
- [x] Hyperdrive config → Neon; KV namespace; paste IDs into `apps/web/wrangler.jsonc`
- [x] `wrangler login`; first deploy; bind crewgraphs.com custom domain
- [ ] CF Access policy on `/admin/*` (deferred with the admin UI itself)

**Phase 0 exit:** scaffold green, spike report reviewed, concept-map go/no-go decided, docs committed.

---

## Phase 1 — Data foundation

### Task 1.1: Core migrations `[terra, sol review]` — DONE (13 migrations as of 2026-07-22)
- [x] `db/migrations/001_schemas_roles.sql` — schemas `core/staging/ops/read/app`, roles + grants (pipeline_rw cannot UPDATE identity tables; web_ro sees `read` only)
- [x] `002_core_identity.sql` — organization, external_identifier (namespace enum incl. reserved `regattacentral_org`), organization_alias, organization_relationship, review_task, audit_event
- [x] `003_core_sources_facts.sql` — source_record, ein_observation, epostcard_observation, filing, financial_fact, concept_definition (seeded with the 24 concepts), person_role, metric_definition/metric_value
- [x] `004_staging_ops.sql` — staging tables, ops.ingest_run/quarantine/publish_snapshot
- [x] `005_read_models.sql` — read.* tables per spec contract + published_snapshot pointer + admin_v views
- [x] Verify: `dbmate up` clean on fresh Postgres; `dbmate rollback` × 5 clean; ci-db green
- 006–013 followed as the pipeline landed (org types, natural keys, grants, metric definitions v1, program mix, person_role.avg_hours_week). Lesson learned twice: always diff applied schema vs spec — workers' migrations dropped spec'd columns.

### Task 1.2: Contracts package hardening `[lead defines, luna implements]` — DONE
- [x] Finalize SourceRef v1 + profile-payload zod schemas from spike learnings; export JSON Schemas; kysely-codegen wired with drift check in ci-web
- [x] Python side: schema-validation test harness in `pipeline/tests/` loading `packages/contracts/schemas/*.json`

### Task 1.3: Fixture cohort `[luna, lead reviews stories]` — DONE
- [x] `db/fixtures/fixtures.sql` — 12 fake orgs covering every state: full 5-yr 990, 990-EZ-only, 990-N-only, missing middle year, amended filing, under_review value, partial metric, single-filing newcomer, legal≠display name, renamed org (slug history), peer-cohort overlaps, zero-revenue year
- [x] Fixture payloads validate against contracts schemas in CI

### Task 1.4: Pipeline run harness `[terra]` — DONE
- [x] `ops.ingest_run` lifecycle wrapper, R2 client (write-once enforcement), config/secrets loading, quarantine writer, Actions job-summary emitter
- [x] Unit tests with a fake R2 (local dir) + ephemeral Postgres

**Phase 1 exit (gate): PASSED** — migrations + contracts + regenerated types + fixtures landed; ci-web/ci-db/ci-ingest green.

---

## Phase 2+ (planned, not detailed here)

Phase 2 (IRS vertical slice), Phase 3 (web experience on fixtures), Phase 4 (cohort + integration), Phase 5 (hardening/launch) are specified in the design spec and get their own dated plan docs when their predecessor gates pass. The web track (Phase 3) may start as soon as the Phase 1 gate passes — it depends only on fixtures, not on real ingestion.

> **2026-07-22 note:** Phases 2–3 completed without their own dated plan docs — the work moved faster than the paperwork. Their outcomes, plus the post-MVP detail layer (financial composition, multi-year people, Part VII deep capture), are recorded in `2026-07-22-crewgraphs-post-mvp.md`, which is now the living plan.

## Verification (Phase 0–1)

- Spike: 6 anchor concepts match ProPublica on every checked filing, or every mismatch is explained; report reviewed by owner.
- Scaffold: all six acceptance commands pass; no cloud credentials required for any Phase 0 check.
- Migrations: up/rollback cycles clean; role-separation verified by attempting a forbidden write as `pipeline_rw` and as `web_ro` (both must fail).
- Contracts: JSON Schema round-trip validated from both TS (vitest) and Python (pytest); kysely-codegen drift check fails CI on uncommitted type changes.
