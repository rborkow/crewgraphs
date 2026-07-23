-- migrate:up

-- Results ingestion foundations (spec: docs/superpowers/specs/2026-07-23-results-ingestion-design.md).
-- Supersede model: `revision` lives on core.regatta only; each re-load inserts a
-- fresh regatta row (revision+1) and a full child tree scoped by FK, so
-- latest-wins reads pick max(revision) and follow FKs. No child bookkeeping.

ALTER TYPE core.source_type ADD VALUE 'herenow';
ALTER TYPE core.source_type ADD VALUE 'time_team';
ALTER TYPE core.source_type ADD VALUE 'row2k';
ALTER TYPE core.source_type ADD VALUE 'regattatiming';
ALTER TYPE core.source_type ADD VALUE 'crewtimer';

-- Only Time-Team has a verified stable native club ID today; name-only
-- providers route through organization_alias instead of a namespace.
ALTER TYPE core.identifier_namespace ADD VALUE 'time_team_club';

CREATE TABLE core.provider_club (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source core.source_type NOT NULL,
  external_key text NOT NULL,
  display_name text NOT NULL,
  code text,
  federation text,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_record_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT provider_club_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT provider_club_source_external_key_uniq UNIQUE (source, external_key)
);
COMMENT ON TABLE core.provider_club IS
  'Provider-side club observation. The org link lives only in curator-owned core.external_identifier (namespace time_team_club) or organization_alias.';
CREATE INDEX provider_club_display_name_idx ON core.provider_club (lower(display_name));

CREATE TABLE core.regatta (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source core.source_type NOT NULL,
  external_key text NOT NULL,
  revision integer NOT NULL DEFAULT 1,
  name text NOT NULL,
  start_date date,
  end_date date,
  venue text,
  city text,
  state text,
  category text,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  payload_checksum text NOT NULL,
  source_record_id uuid,
  parser_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regatta_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT regatta_source_external_revision_uniq UNIQUE (source, external_key, revision),
  CONSTRAINT regatta_date_range_check
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);
COMMENT ON TABLE core.regatta IS
  'One provider regatta payload capture; payload_checksum makes an unchanged re-load a no-op instead of a new revision.';
CREATE INDEX regatta_source_external_key_idx ON core.regatta (source, external_key);
CREATE INDEX regatta_start_date_idx ON core.regatta (start_date);

CREATE TABLE core.regatta_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  regatta_id uuid NOT NULL,
  external_key text NOT NULL,
  name text NOT NULL,
  event_code text,
  boat_class_raw text,
  age_class_raw text,
  gender_raw text,
  round text,
  scheduled_at timestamptz,
  progression jsonb NOT NULL DEFAULT '[]'::jsonb,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regatta_event_regatta_fk
    FOREIGN KEY (regatta_id) REFERENCES core.regatta(id),
  CONSTRAINT regatta_event_regatta_external_key_uniq UNIQUE (regatta_id, external_key)
);
COMMENT ON TABLE core.regatta_event IS
  'Provider-raw classification only; canonical boat class / age bracket / gender land in the versioned event_classification table (Wave 3).';
CREATE INDEX regatta_event_regatta_id_idx ON core.regatta_event (regatta_id);

CREATE TABLE core.regatta_entry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  external_key text NOT NULL,
  bib text,
  lane integer,
  club_source_name text NOT NULL,
  provider_club_id uuid,
  crew_label text,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regatta_entry_event_fk
    FOREIGN KEY (event_id) REFERENCES core.regatta_event(id),
  CONSTRAINT regatta_entry_provider_club_fk
    FOREIGN KEY (provider_club_id) REFERENCES core.provider_club(id),
  CONSTRAINT regatta_entry_event_external_key_uniq UNIQUE (event_id, external_key)
);
COMMENT ON TABLE core.regatta_entry IS
  'club_source_name keeps the provider string verbatim even once provider_club resolves. Person names live only in core.result_person.';
CREATE INDEX regatta_entry_event_id_idx ON core.regatta_entry (event_id);
CREATE INDEX regatta_entry_provider_club_id_idx ON core.regatta_entry (provider_club_id);

CREATE TABLE core.regatta_result (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_id uuid NOT NULL,
  status text NOT NULL,
  position integer,
  adjusted_position integer,
  time_ms bigint,
  adjusted_time_ms bigint,
  handicap_ms bigint,
  delta_ms bigint,
  penalty jsonb,
  correction jsonb,
  splits jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regatta_result_entry_fk
    FOREIGN KEY (entry_id) REFERENCES core.regatta_entry(id),
  CONSTRAINT regatta_result_entry_uniq UNIQUE (entry_id),
  CONSTRAINT regatta_result_time_sanity_check
    CHECK (time_ms IS NULL OR time_ms > 0)
);
COMMENT ON TABLE core.regatta_result IS
  'status keeps the provider vocabulary raw (DNS/DNF/DSQ/withdrawn/relegated/OOC…); normalization is a publish concern.';

CREATE TABLE core.result_person (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entry_id uuid NOT NULL,
  role text NOT NULL,
  seat integer,
  person_name text NOT NULL,
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT result_person_entry_fk
    FOREIGN KEY (entry_id) REFERENCES core.regatta_entry(id)
);
COMMENT ON TABLE core.result_person IS
  'The only person-level store for results (PII policy 2026-07-23). FK points at the entry so this table is purgeable without touching results.';
CREATE INDEX result_person_entry_id_idx ON core.result_person (entry_id);

CREATE TABLE core.person_suppression (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_name_normalized text NOT NULL,
  source core.source_type,
  provider_club_id uuid,
  reason text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT person_suppression_provider_club_fk
    FOREIGN KEY (provider_club_id) REFERENCES core.provider_club(id)
);
COMMENT ON TABLE core.person_suppression IS
  'Curator-only takedown list; publish redacts matching names (optionally scoped to a source/club). NULL scope = global.';
CREATE INDEX person_suppression_name_idx ON core.person_suppression (person_name_normalized);

-- Staging for the Wave-1 JSON adapters (row2k/regattatiming stage with their
-- own migrations, 015/016).

CREATE TABLE staging.herenow_catalog_row (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  race_id bigint NOT NULL,
  raw_row jsonb NOT NULL,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT herenow_catalog_row_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT herenow_catalog_row_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT herenow_catalog_row_race_id_uniq UNIQUE (race_id)
);
CREATE INDEX herenow_catalog_row_ingest_run_id_idx ON staging.herenow_catalog_row (ingest_run_id);

CREATE TABLE staging.herenow_race_payload (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  race_id bigint NOT NULL,
  kind text NOT NULL,
  raw_payload jsonb NOT NULL,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT herenow_race_payload_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT herenow_race_payload_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT herenow_race_payload_kind_check CHECK (kind IN ('base', 'flights')),
  CONSTRAINT herenow_race_payload_race_kind_uniq UNIQUE (race_id, kind)
);
CREATE INDEX herenow_race_payload_ingest_run_id_idx ON staging.herenow_race_payload (ingest_run_id);

CREATE TABLE staging.time_team_regatta (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  slug text NOT NULL,
  year integer NOT NULL,
  raw_payload jsonb,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT time_team_regatta_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT time_team_regatta_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT time_team_regatta_slug_year_uniq UNIQUE (slug, year)
);
COMMENT ON TABLE staging.time_team_regatta IS
  'raw_payload is NULL between index discovery and race-sync fetching the schedule doc.';
CREATE INDEX time_team_regatta_ingest_run_id_idx ON staging.time_team_regatta (ingest_run_id);

CREATE TABLE staging.time_team_race (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  slug text NOT NULL,
  year integer NOT NULL,
  race_uuid uuid NOT NULL,
  raw_payload jsonb NOT NULL,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT time_team_race_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT time_team_race_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT time_team_race_race_uuid_uniq UNIQUE (race_uuid)
);
CREATE INDEX time_team_race_ingest_run_id_idx ON staging.time_team_race (ingest_run_id);
CREATE INDEX time_team_race_slug_year_idx ON staging.time_team_race (slug, year);

-- Replace the grants routine with the results tables appended (001/008
-- pattern). person_suppression is curator-write / pipeline-read (publish must
-- read it to redact); result_person additionally gets a belt-and-braces
-- web_ro revoke even though web_ro holds no core grants.
CREATE OR REPLACE FUNCTION app.apply_phase1_role_grants()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA core, staging, ops, read, app TO pipeline_rw';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging, ops, read, app TO pipeline_rw';
    IF to_regclass('core.financial_fact') IS NOT NULL THEN
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.financial_fact, core.filing, core.source_record, core.ein_observation, core.epostcard_observation, core.person_role, core.metric_value FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.financial_fact, core.filing, core.source_record, core.ein_observation, core.epostcard_observation, core.person_role, core.metric_value TO pipeline_rw';
      EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE core.organization, core.external_identifier, core.organization_alias, core.organization_relationship FROM pipeline_rw';
    END IF;
    IF to_regclass('core.regatta') IS NOT NULL THEN
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person TO pipeline_rw';
      EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE core.person_suppression FROM pipeline_rw';
      EXECUTE 'GRANT SELECT ON TABLE core.person_suppression TO pipeline_rw';
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'curator') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA core TO curator';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core TO curator';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_ro') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA read TO web_ro';
    EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA read TO web_ro';
    IF to_regclass('core.result_person') IS NOT NULL THEN
      EXECUTE 'REVOKE ALL ON TABLE core.result_person, core.person_suppression FROM web_ro';
    END IF;
  END IF;
END;
$$;

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

DROP TABLE staging.time_team_race;
DROP TABLE staging.time_team_regatta;
DROP TABLE staging.herenow_race_payload;
DROP TABLE staging.herenow_catalog_row;
DROP TABLE core.person_suppression;
DROP TABLE core.result_person;
DROP TABLE core.regatta_result;
DROP TABLE core.regatta_entry;
DROP TABLE core.regatta_event;
DROP TABLE core.regatta;
DROP TABLE core.provider_club;

-- Restore the 001 body of the grants routine (rollback/reapply in CI runs all
-- downs then all ups; state after this down must match state after 013 up).
CREATE OR REPLACE FUNCTION app.apply_phase1_role_grants()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA core, staging, ops, read, app TO pipeline_rw';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging, ops, read, app TO pipeline_rw';
    IF to_regclass('core.financial_fact') IS NOT NULL THEN
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.financial_fact, core.filing, core.source_record, core.ein_observation, core.epostcard_observation, core.person_role, core.metric_value FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.financial_fact, core.filing, core.source_record, core.ein_observation, core.epostcard_observation, core.person_role, core.metric_value TO pipeline_rw';
      EXECUTE 'REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON TABLE core.organization, core.external_identifier, core.organization_alias, core.organization_relationship FROM pipeline_rw';
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'curator') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA core TO curator';
    EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core TO curator';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_ro') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA read TO web_ro';
    EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA read TO web_ro';
  END IF;
END;
$$;

ALTER TYPE core.identifier_namespace RENAME TO identifier_namespace_results;
CREATE TYPE core.identifier_namespace AS ENUM (
  'irs_ein', 'propublica_ein', 'website_domain', 'usrowing', 'regattacentral_org'
);
ALTER TABLE core.external_identifier
  ALTER COLUMN namespace TYPE core.identifier_namespace
  USING (namespace::text::core.identifier_namespace);
DROP TYPE core.identifier_namespace_results;

ALTER TYPE core.source_type RENAME TO source_type_results;
CREATE TYPE core.source_type AS ENUM (
  'irs_bmf', 'irs_efile_index', 'irs_990_xml', 'irs_990n', 'propublica', 'givingtuesday'
);
ALTER TABLE core.source_record
  ALTER COLUMN source TYPE core.source_type
  USING (source::text::core.source_type);
DROP TYPE core.source_type_results;
