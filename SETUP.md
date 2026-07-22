# CrewGraphs owner setup

Status as of 2026-07-21: steps 1–4, 6, and 7 are DONE (Hyperdrive `crewgraphs-web` → Neon as `web_ro`; KV `crewgraphs-web`; crewgraphs.com + www bound; deployed). Remaining: the Neon role fix below, GitHub secrets (step 5, needed before Phase 2 cloud ingestion), and the `/admin/*` Access policy (step 8, needed before the admin routes exist).

## Required: recreate Neon roles via SQL

The `pipeline_rw` / `curator` / `web_ro` roles were created in the Neon console, which makes them members of `neon_superuser` — that membership carries `pg_read_all_data`/`pg_write_all_data` and silently bypasses the grant-based role separation the migrations set up. `neondb_owner` cannot demote or drop console-created roles, so:

1. In the Neon console (Branches → Roles), **delete** `pipeline_rw`, `curator`, and `web_ro`.
2. Recreate them via SQL as `neondb_owner` with the same passwords already in `.env` (SQL-created roles are plain roles, and keeping the `web_ro` password unchanged means the Hyperdrive config keeps working without edits):

```sql
CREATE ROLE pipeline_rw LOGIN PASSWORD '<NEON_PIPELINE_RW_ROLE_PASSWORD>';
CREATE ROLE curator     LOGIN PASSWORD '<NEON_CURATOR_ROLE_PASSWORD>';
CREATE ROLE web_ro      LOGIN PASSWORD '<NEON_WEB_RO_ROLE_PASSWORD>';
SELECT app.apply_phase1_role_grants();
```

3. Verify separation (all should hold): `pipeline_rw` cannot UPDATE `core.organization`; `web_ro` sees only the `read` schema; `curator` has full DML on `core`. (Claude can run the recreation + verification once the console roles are deleted.)

## Original checklist

1. ~~Create a Neon project and the `pipeline_rw`, `curator`, and `web_ro` database roles.~~ DONE (see role fix above).
2. ~~Create the Cloudflare R2 bucket `crewgraphs-raw`.~~ DONE.
3. ~~Create a Cloudflare Hyperdrive configuration pointing at Neon, then paste its ID into `apps/web/wrangler.jsonc`.~~ DONE (`crewgraphs-web`, connects as `web_ro`; no VPC/tunnel — Neon's public TLS endpoint with password auth).
4. ~~Create a Cloudflare KV namespace, then paste its ID into `apps/web/wrangler.jsonc`.~~ DONE (`crewgraphs-web`).
5. Add GitHub secrets to `rborkow/crewgraphs`: `NEON_DATABASE_URL`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`. (R2 API token: Cloudflare dashboard → R2 → Manage API Tokens → Object Read & Write scoped to `crewgraphs-raw`.) Needed before Phase 2 cloud ingestion; CI runs without them.
6. ~~Run `wrangler login` on the owner workstation.~~ DONE.
7. ~~Bind `crewgraphs.com` to the Worker with a Cloudflare custom domain.~~ DONE (apex + www, via `routes` in wrangler.jsonc).
8. Add a Cloudflare Access policy for `/admin/*` for the owner email. (Do when admin routes land in Phase 3.)

## Local development notes

- `.env` (gitignored) holds `DATABASE_URL`, the three role passwords, and `CLOUDFLARE_HYPERDRIVE_LOCAL_CONNECTION_STRING_HYPERDRIVE` (used by wrangler/miniflare to emulate the Hyperdrive binding locally and during `opennextjs-cloudflare deploy`). See `.env.example`.
- Deploy: `cd apps/web && bun run build:worker && bun run deploy` (with `.env` sourced).
- Migrations: `dbmate up` / `dbmate rollback` from the repo root with `.env` sourced; schema dump convention is `db/schema.sql` (requires `pg_dump`, e.g. `brew install libpq`).
