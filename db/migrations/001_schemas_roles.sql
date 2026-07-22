-- migrate:up

CREATE SCHEMA core;
CREATE SCHEMA staging;
CREATE SCHEMA ops;
CREATE SCHEMA read;
CREATE SCHEMA app;

-- This routine is deliberately idempotent and only grants to roles present in
-- the target cluster. It is invoked again after all Phase 1 tables exist.
CREATE FUNCTION app.apply_phase1_role_grants()
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

REVOKE EXECUTE ON FUNCTION app.apply_phase1_role_grants() FROM PUBLIC;

-- CI's service container has no application roles, so this is intentionally guarded.
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

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'REVOKE ALL PRIVILEGES ON SCHEMA core, staging, ops, read, app FROM pipeline_rw';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'curator') THEN
    EXECUTE 'REVOKE ALL PRIVILEGES ON SCHEMA core FROM curator';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_ro') THEN
    EXECUTE 'REVOKE ALL PRIVILEGES ON SCHEMA read FROM web_ro';
  END IF;
END;
$$;

DROP FUNCTION app.apply_phase1_role_grants();
DROP SCHEMA app;
DROP SCHEMA read;
DROP SCHEMA ops;
DROP SCHEMA staging;
DROP SCHEMA core;
