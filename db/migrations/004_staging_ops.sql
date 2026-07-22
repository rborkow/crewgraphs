-- migrate:up

CREATE TYPE ops.ingest_run_status AS ENUM ('running', 'succeeded', 'failed', 'partial');
CREATE TYPE ops.publish_snapshot_status AS ENUM ('building', 'active', 'superseded', 'rolled_back');

CREATE TABLE staging.bmf_row (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  bmf_release_date date NOT NULL,
  ein text,
  raw_row jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE staging.bmf_row IS 'Unnormalized row from one BMF release.';
CREATE INDEX bmf_row_ingest_run_id_idx ON staging.bmf_row (ingest_run_id);
CREATE INDEX bmf_row_source_record_id_idx ON staging.bmf_row (source_record_id);
CREATE INDEX bmf_row_ein_idx ON staging.bmf_row (ein);

CREATE TABLE staging.efile_index_row (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  tax_year integer NOT NULL,
  ein text,
  irs_object_id text NOT NULL,
  xml_batch_id text NOT NULL,
  raw_row jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE staging.efile_index_row IS 'IRS index row retaining the XML batch identifier for fallback fetches.';
CREATE INDEX efile_index_row_ingest_run_id_idx ON staging.efile_index_row (ingest_run_id);
CREATE INDEX efile_index_row_source_record_id_idx ON staging.efile_index_row (source_record_id);
CREATE INDEX efile_index_row_ein_idx ON staging.efile_index_row (ein);
CREATE INDEX efile_index_row_object_id_idx ON staging.efile_index_row (irs_object_id);

CREATE TABLE staging.filing_extract (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid NOT NULL,
  ein text NOT NULL,
  irs_object_id text NOT NULL,
  concepts jsonb NOT NULL DEFAULT '{}'::jsonb,
  people jsonb NOT NULL DEFAULT '[]'::jsonb,
  warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX filing_extract_ingest_run_id_idx ON staging.filing_extract (ingest_run_id);
CREATE INDEX filing_extract_source_record_id_idx ON staging.filing_extract (source_record_id);
CREATE INDEX filing_extract_ein_object_id_idx ON staging.filing_extract (ein, irs_object_id);

CREATE TABLE staging.epostcard_row (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  ein text,
  raw_row jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX epostcard_row_ingest_run_id_idx ON staging.epostcard_row (ingest_run_id);
CREATE INDEX epostcard_row_source_record_id_idx ON staging.epostcard_row (source_record_id);
CREATE INDEX epostcard_row_ein_idx ON staging.epostcard_row (ein);

CREATE TABLE staging.propublica_org (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  ein text NOT NULL,
  raw_payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX propublica_org_ingest_run_id_idx ON staging.propublica_org (ingest_run_id);
CREATE INDEX propublica_org_source_record_id_idx ON staging.propublica_org (source_record_id);
CREATE INDEX propublica_org_ein_idx ON staging.propublica_org (ein);

CREATE TABLE ops.ingest_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_name text NOT NULL,
  git_sha text NOT NULL,
  code_version text NOT NULL,
  params jsonb NOT NULL DEFAULT '{}'::jsonb,
  stats jsonb NOT NULL DEFAULT '{}'::jsonb,
  status ops.ingest_run_status NOT NULL DEFAULT 'running',
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ingest_run_finished_at_check CHECK (finished_at IS NULL OR finished_at >= started_at)
);
CREATE INDEX ingest_run_job_name_created_at_idx ON ops.ingest_run (job_name, created_at DESC);
CREATE INDEX ingest_run_status_idx ON ops.ingest_run (status);

CREATE TABLE ops.quarantine (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  reason text NOT NULL,
  raw_uri text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  resolved boolean NOT NULL DEFAULT false,
  resolved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT quarantine_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT quarantine_resolved_at_check CHECK (NOT resolved OR resolved_at IS NOT NULL)
);
CREATE INDEX quarantine_ingest_run_id_idx ON ops.quarantine (ingest_run_id);
CREATE INDEX quarantine_unresolved_idx ON ops.quarantine (created_at) WHERE NOT resolved;

CREATE TABLE ops.publish_snapshot (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  status ops.publish_snapshot_status NOT NULL DEFAULT 'building',
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  activated_at timestamptz,
  CONSTRAINT publish_snapshot_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id)
);
CREATE INDEX publish_snapshot_ingest_run_id_idx ON ops.publish_snapshot (ingest_run_id);
CREATE INDEX publish_snapshot_status_idx ON ops.publish_snapshot (status);

ALTER TABLE staging.bmf_row
  ADD CONSTRAINT bmf_row_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  ADD CONSTRAINT bmf_row_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);
ALTER TABLE staging.efile_index_row
  ADD CONSTRAINT efile_index_row_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  ADD CONSTRAINT efile_index_row_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);
ALTER TABLE staging.filing_extract
  ADD CONSTRAINT filing_extract_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  ADD CONSTRAINT filing_extract_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);
ALTER TABLE staging.epostcard_row
  ADD CONSTRAINT epostcard_row_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  ADD CONSTRAINT epostcard_row_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);
ALTER TABLE staging.propublica_org
  ADD CONSTRAINT propublica_org_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  ADD CONSTRAINT propublica_org_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);

-- migrate:down

DROP TABLE staging.propublica_org;
DROP TABLE staging.epostcard_row;
DROP TABLE staging.filing_extract;
DROP TABLE staging.efile_index_row;
DROP TABLE staging.bmf_row;
DROP TABLE ops.publish_snapshot;
DROP TABLE ops.quarantine;
DROP TABLE ops.ingest_run;
DROP TYPE ops.publish_snapshot_status;
DROP TYPE ops.ingest_run_status;
