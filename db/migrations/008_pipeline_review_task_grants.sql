-- migrate:up

-- Pipeline jobs must be able to open review tasks (cross_check mismatches,
-- parse anomalies) and append audit events (deterministic auto-attach), but
-- never resolve tasks or mutate identity rows — those stay curator-only.
CREATE OR REPLACE FUNCTION app.apply_phase2_pipeline_grants()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'GRANT SELECT, INSERT ON TABLE core.review_task, core.audit_event TO pipeline_rw';
    EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.review_task, core.audit_event FROM pipeline_rw';
    -- resolve reads identity tables to find verified EINs; reading is safe.
    EXECUTE 'GRANT SELECT ON TABLE core.organization, core.external_identifier, core.organization_alias, core.organization_relationship TO pipeline_rw';
    EXECUTE 'GRANT SELECT ON TABLE core.concept_definition, core.metric_definition TO pipeline_rw';
  END IF;
END;
$$;

REVOKE EXECUTE ON FUNCTION app.apply_phase2_pipeline_grants() FROM PUBLIC;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    PERFORM app.apply_phase2_pipeline_grants();
  END IF;
END;
$$;

-- migrate:down

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'REVOKE ALL PRIVILEGES ON TABLE core.review_task, core.audit_event FROM pipeline_rw';
    EXECUTE 'REVOKE SELECT ON TABLE core.organization, core.external_identifier, core.organization_alias, core.organization_relationship FROM pipeline_rw';
    EXECUTE 'REVOKE SELECT ON TABLE core.concept_definition, core.metric_definition FROM pipeline_rw';
  END IF;
END;
$$;

DROP FUNCTION app.apply_phase2_pipeline_grants();
