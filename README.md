# CrewGraphs

A trusted, rowing-native reference for club identity, participation, and financial context. FanGraphs energy, Form 990 rigor.

See docs/superpowers/ for design specs and build plans, and SETUP.md for owner setup steps.

## Status: archived (2026-10-18)

The project is wound down. The scheduled pipelines (`irs-backfill.yml`, `results-backfill.yml`) are disabled, and the Neon database and crewgraphs.com deployment are being retired.

**Data:** a full `pg_dump` of the production database (Postgres 18, custom format, `--no-owner --no-privileges`, 51 tables / 2,551,558 rows, verified by a full restore) is kept outside the repo as `crewgraphs-2026-10-18.dump`, sha256 `897aa57c12a2a9c43c3897d39b6d66a39af96d7c1b0a5bcaedf31e9058ff9d36`. A roles-only dump (no passwords) sits alongside it. Raw source filings were in the R2 bucket `crewgraphs-raw`.

**To revive:**

1. Create a Postgres 18 database and recreate the roles (`web_ro`, `pipeline_rw`, `curator`, `admin_ro`) per SETUP.md.
2. Run `pg_restore --no-owner --no-privileges -d <url> crewgraphs-2026-10-18.dump`, then re-apply grants.
3. Point a new Hyperdrive config at the database, update `apps/web/wrangler.jsonc`, then `npm run build:worker && npm run deploy`.
4. Re-enable the workflows with `gh workflow enable` and reset the GitHub secrets.
