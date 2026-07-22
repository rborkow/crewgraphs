-- migrate:up

-- The spec gives ops.ingest_run first-class source and error fields
-- (freshness dashboards group by source; error triage reads error), but 004
-- omitted them and the harness had been packing both into jsonb.
ALTER TABLE ops.ingest_run ADD COLUMN source text;
ALTER TABLE ops.ingest_run ADD COLUMN error text;
CREATE INDEX ingest_run_source_idx ON ops.ingest_run (source, started_at DESC);

-- migrate:down

DROP INDEX ops.ingest_run_source_idx;
ALTER TABLE ops.ingest_run DROP COLUMN error;
ALTER TABLE ops.ingest_run DROP COLUMN source;
