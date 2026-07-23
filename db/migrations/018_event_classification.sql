-- migrate:up

CREATE TABLE core.event_classification (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL REFERENCES core.regatta_event(id),
  mapping_version text NOT NULL,
  boat_class text NOT NULL CHECK (boat_class IN ('1x', '2x', '2-', '2+', '4x', '4-', '4+', '8+', 'other')),
  age_bracket text NOT NULL CHECK (age_bracket IN (
    'u13', 'u15', 'u16', 'u17', 'u19_youth', 'collegiate', 'open',
    'masters_a', 'masters_b', 'masters_c', 'masters_d', 'masters_e',
    'masters_f', 'masters_g', 'masters_h', 'masters_i', 'masters_j',
    'masters_k', 'masters_unspecified', 'other'
  )),
  gender text NOT NULL CHECK (gender IN ('men', 'women', 'mixed', 'open', 'unspecified')),
  mapping_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT event_classification_event_mapping_version_uniq UNIQUE (event_id, mapping_version)
);
CREATE INDEX event_classification_event_id_idx ON core.event_classification (event_id);
COMMENT ON TABLE core.event_classification IS
  'Insert-only canonical event mapping; latest mapping_version wins in reads.';

-- 015 owns the latest grants-function body. Append this table to its
-- insert-only results family; 016 and 017 only invoke the function.
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
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link, core.event_classification FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link, core.event_classification TO pipeline_rw';
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

DROP TABLE core.event_classification;

-- Restore the exact grants routine body from 015. Rollback/reapply must leave
-- the function state that migration 017 inherited before this migration.
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
