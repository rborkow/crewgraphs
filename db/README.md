# Database migrations

Install [dbmate](https://github.com/amacneil/dbmate), set `DATABASE_URL` from the repository `.env.example`, then apply migrations with:

```sh
dbmate up
```

After changing migrations, update the checked-in schema dump with:

```sh
dbmate dump
```

The schema dump convention is `db/schema.sql`.

## Migration map

- `001_schemas_roles.sql` — creates Phase 1 schemas and the guarded application-role grant routine.
- `002_core_identity.sql` — canonical organizations, identifiers, aliases, relationships, review tasks, and audit events.
- `003_core_sources_facts.sql` — immutable sources, observations, filings, financial concepts/facts, people, and metrics.
- `004_staging_ops.sql` — raw staging rows plus ingestion, quarantine, and publish operations.
- `005_read_models.sql` — snapshot-scoped public read models, corrections, and admin views.

### Grants approach

`001` contains the only `GRANT`/`REVOKE` statements, inside an idempotent routine that checks `pg_roles` before naming each login role. `005` invokes it after all Phase 1 tables exist, so `pipeline_rw` receives DML on `staging`, `ops`, `read`, and `app`, but only `SELECT`/`INSERT` on the listed core fact tables; explicit revokes reinforce that it has no identity-table writes. `curator` receives core DML and `web_ro` receives only `read` usage/select access. Role-less CI containers skip all grants safely.
