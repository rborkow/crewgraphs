-- migrate:up

CREATE SCHEMA admin_v;

CREATE TYPE read.coverage_state AS ENUM ('990', '990ez', '990n_only', 'none');
CREATE TYPE read.filing_coverage_status AS ENUM ('990', '990ez', '990n', 'amended', 'missing', 'not_yet_expected');
CREATE TYPE read.series_quality_state AS ENUM ('verified', 'derived', 'partial', 'unavailable', 'under_review');

CREATE TABLE read.published_snapshot (
  singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  snapshot_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT published_snapshot_snapshot_fk
    FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id)
);
COMMENT ON TABLE read.published_snapshot IS 'Single-row pointer atomically selecting the public read-model snapshot.';
CREATE INDEX published_snapshot_snapshot_id_idx ON read.published_snapshot (snapshot_id);

CREATE TABLE read.org_directory (
  snapshot_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  slug text NOT NULL,
  display_name text NOT NULL,
  coverage_state read.coverage_state NOT NULL,
  aliases jsonb NOT NULL DEFAULT '[]'::jsonb,
  search_text tsvector NOT NULL DEFAULT ''::tsvector,
  fye_month integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, organization_id),
  CONSTRAINT org_directory_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_directory_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT org_directory_snapshot_slug_uniq UNIQUE (snapshot_id, slug),
  CONSTRAINT org_directory_fye_month_check CHECK (fye_month BETWEEN 1 AND 12 OR fye_month IS NULL)
);
CREATE INDEX org_directory_organization_id_idx ON read.org_directory (organization_id);
CREATE INDEX org_directory_search_text_idx ON read.org_directory USING gin (search_text);

CREATE TABLE read.org_profile (
  snapshot_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  payload jsonb NOT NULL,
  payload_schema_version integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, organization_id),
  CONSTRAINT org_profile_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_profile_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id)
);
COMMENT ON TABLE read.org_profile IS 'Versioned public profile payload.';
CREATE INDEX org_profile_organization_id_idx ON read.org_profile (organization_id);

CREATE TABLE read.org_financial_series (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  series_key text NOT NULL,
  series_version integer NOT NULL,
  tax_year integer NOT NULL,
  fiscal_year_end date NOT NULL,
  value numeric(16,2),
  quality_state read.series_quality_state NOT NULL,
  is_amended boolean NOT NULL DEFAULT false,
  source_ref jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_financial_series_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_financial_series_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT org_financial_series_snapshot_series_uniq
    UNIQUE (snapshot_id, organization_id, series_key, series_version, tax_year)
);
COMMENT ON TABLE read.org_financial_series IS 'Long-form values; source_ref accommodates the contracts SourceRef provenance object.';
CREATE INDEX org_financial_series_snapshot_id_idx ON read.org_financial_series (snapshot_id);
CREATE INDEX org_financial_series_organization_id_idx ON read.org_financial_series (organization_id);
CREATE INDEX org_financial_series_tax_year_idx ON read.org_financial_series (tax_year);

CREATE TABLE read.org_filing_coverage (
  snapshot_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  tax_year integer NOT NULL,
  status read.filing_coverage_status NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, organization_id, tax_year),
  CONSTRAINT org_filing_coverage_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_filing_coverage_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id)
);
CREATE INDEX org_filing_coverage_organization_id_idx ON read.org_filing_coverage (organization_id);
CREATE INDEX org_filing_coverage_tax_year_idx ON read.org_filing_coverage (tax_year);

CREATE TABLE read.org_peer_cohort (
  snapshot_id uuid NOT NULL,
  organization_id uuid NOT NULL,
  cohort_key text NOT NULL,
  reason_labels jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, organization_id, cohort_key),
  CONSTRAINT org_peer_cohort_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_peer_cohort_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id)
);
CREATE INDEX org_peer_cohort_organization_id_idx ON read.org_peer_cohort (organization_id);
CREATE INDEX org_peer_cohort_cohort_key_idx ON read.org_peer_cohort (cohort_key);

CREATE TABLE read.metric_catalog (
  snapshot_id uuid NOT NULL,
  metric_key text NOT NULL,
  metric_version integer NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, metric_key, metric_version),
  CONSTRAINT metric_catalog_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id)
);

CREATE TABLE read.source_registry_public (
  snapshot_id uuid NOT NULL,
  source_key text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (snapshot_id, source_key),
  CONSTRAINT source_registry_public_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id)
);

CREATE TABLE read.org_slug_history (
  slug text PRIMARY KEY,
  snapshot_id uuid NOT NULL,
  org_id uuid NOT NULL,
  is_current boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_slug_history_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id),
  CONSTRAINT org_slug_history_org_fk FOREIGN KEY (org_id) REFERENCES core.organization(id)
);
COMMENT ON TABLE read.org_slug_history IS 'Slugs are globally unique and never reused.';
CREATE INDEX org_slug_history_snapshot_id_idx ON read.org_slug_history (snapshot_id);
CREATE INDEX org_slug_history_org_id_idx ON read.org_slug_history (org_id);
CREATE UNIQUE INDEX org_slug_history_current_org_uniq ON read.org_slug_history (org_id) WHERE is_current;

CREATE TABLE app.correction_submission (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid,
  submitter_email text,
  message text NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT correction_submission_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT correction_submission_status_check CHECK (status IN ('pending', 'reviewed', 'resolved', 'rejected'))
);
CREATE INDEX correction_submission_organization_id_idx ON app.correction_submission (organization_id);
CREATE INDEX correction_submission_status_idx ON app.correction_submission (status);

CREATE VIEW admin_v.review_task AS
  SELECT * FROM core.review_task;
CREATE VIEW admin_v.audit_event AS
  SELECT * FROM core.audit_event;

-- All table grants are executed only after every Phase 1 table exists. The
-- routine itself checks pg_roles, keeping role-less CI containers portable.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname IN ('pipeline_rw', 'curator', 'web_ro')
  ) THEN
    PERFORM app.apply_phase1_role_grants();
  END IF;
END;
$$;

-- migrate:down

DROP VIEW admin_v.audit_event;
DROP VIEW admin_v.review_task;
DROP TABLE app.correction_submission;
DROP TABLE read.org_slug_history;
DROP TABLE read.source_registry_public;
DROP TABLE read.metric_catalog;
DROP TABLE read.org_peer_cohort;
DROP TABLE read.org_filing_coverage;
DROP TABLE read.org_financial_series;
DROP TABLE read.org_profile;
DROP TABLE read.org_directory;
DROP TABLE read.published_snapshot;
DROP TYPE read.series_quality_state;
DROP TYPE read.filing_coverage_status;
DROP TYPE read.coverage_state;
DROP SCHEMA admin_v;
