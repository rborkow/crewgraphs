-- migrate:up

-- row2k is a discovery registry only. Its results-page policy permits copying
-- by schools/clubs of their own results; everyone else links and credits row2k.
CREATE TABLE staging.row2k_index_page (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid,
  source_record_id uuid,
  year integer NOT NULL,
  category text,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT row2k_index_page_ingest_run_fk
    FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id),
  CONSTRAINT row2k_index_page_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id)
);
CREATE INDEX row2k_index_page_ingest_run_id_idx
  ON staging.row2k_index_page (ingest_run_id);

CREATE TABLE core.regatta_source_link (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  regatta_name text NOT NULL,
  event_date date,
  category text,
  location text,
  outbound_url text NOT NULL,
  outbound_host text NOT NULL,
  provider core.source_type,
  credit_url text NOT NULL,
  source_record_id uuid,
  retrieved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regatta_source_link_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT regatta_source_link_event_date_outbound_url_uniq
    UNIQUE NULLS NOT DISTINCT (event_date, outbound_url)
);
COMMENT ON TABLE core.regatta_source_link IS
  'row2k discovery facts and outbound links only; never result content, per row2k link-don''t-copy policy.';

-- Replace the grants routine with the 014 body and append the row2k registry
-- to the results family. staging.row2k_index_page is covered by the existing
-- blanket staging grant.
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
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link TO pipeline_rw';
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

DROP TABLE core.regatta_source_link;
DROP TABLE staging.row2k_index_page;

-- Restore the exact grants routine body from 014. Rollback/reapply in CI must
-- leave the same function that migration 015 installed.
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
