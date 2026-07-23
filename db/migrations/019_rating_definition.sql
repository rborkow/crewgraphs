-- migrate:up

-- Ratings remain draft product content until the R3 held-out backtest is
-- checked in.  The derive job computes every linked program; eligibility_met
-- is the durable publication gate for a later wave.
INSERT INTO core.metric_definition
  (metric_key, version, label, description, unit, eligibility_rule, limitation, status)
VALUES
  (
    'rating_rof',
    1,
    'Rank-ordered-field rating',
    'Seasonal program strength estimated from full ranked fields with a regularized Plackett-Luce model.',
    'rating',
    '{"min_ranked_fields": 5, "min_distinct_regattas": 2, "min_field_size": 3}'::jsonb,
    'Draft pending the R3 held-out finish-order backtest. The display scale is relative; organizations linked to multiple provider clubs use method=appearance_weighted_mean; rating_sigma is an appearance-count uncertainty proxy rather than a calibrated interval.',
    'draft'
  );

-- metric_value is intentionally not used: its uniqueness key cannot represent
-- multiple boat-class/age/gender programs for one organization and season.
-- program_rating carries season explicitly.  If a future compatibility view
-- projects a rating through the IRS-shaped metric_value columns, the required
-- mapping is tax_year = season and fiscal_year_end = season-12-31.
CREATE TABLE core.program_rating (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  season integer NOT NULL,
  boat_class text NOT NULL,
  age_bracket text NOT NULL,
  gender text NOT NULL,
  metric_key text NOT NULL,
  metric_version integer NOT NULL,
  rating numeric NOT NULL,
  rating_sigma numeric NOT NULL,
  ranked_fields integer NOT NULL,
  distinct_regattas integer NOT NULL,
  field_sizes jsonb NOT NULL,
  computation_version text NOT NULL,
  eligibility_met boolean NOT NULL,
  input_summary jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT program_rating_organization_fk
    FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT program_rating_metric_definition_fk
    FOREIGN KEY (metric_key, metric_version)
    REFERENCES core.metric_definition(metric_key, version),
  CONSTRAINT program_rating_season_check
    CHECK (season BETWEEN 1800 AND 9999),
  CONSTRAINT program_rating_rating_sigma_check
    CHECK (rating_sigma >= 0),
  CONSTRAINT program_rating_ranked_fields_check
    CHECK (ranked_fields > 0),
  CONSTRAINT program_rating_distinct_regattas_check
    CHECK (distinct_regattas > 0 AND distinct_regattas <= ranked_fields),
  CONSTRAINT program_rating_field_sizes_check
    CHECK (jsonb_typeof(field_sizes) = 'array'),
  CONSTRAINT program_rating_input_summary_check
    CHECK (jsonb_typeof(input_summary) = 'object'),
  CONSTRAINT program_rating_identity_uniq
    UNIQUE (
      organization_id,
      season,
      boat_class,
      age_bracket,
      gender,
      metric_key,
      metric_version,
      computation_version
    )
);
COMMENT ON TABLE core.program_rating IS
  'Insert-only seasonal program ratings. New computation_version rows supersede analytically without rewriting prior outputs; no row is publishable unless eligibility_met and the metric definition is active.';
COMMENT ON COLUMN core.program_rating.rating_sigma IS
  'Uncalibrated 1/sqrt(ranked-field appearances) proxy pending the R3 backtest; not a confidence interval.';
COMMENT ON COLUMN core.program_rating.input_summary IS
  'Deterministic, aggregate-only model inputs and settings. Person names are prohibited by job construction.';
CREATE INDEX program_rating_metric_definition_idx
  ON core.program_rating (metric_key, metric_version);
CREATE INDEX program_rating_organization_season_idx
  ON core.program_rating (organization_id, season);
CREATE INDEX program_rating_program_idx
  ON core.program_rating (season, boat_class, age_bracket, gender);
CREATE INDEX program_rating_eligible_idx
  ON core.program_rating (metric_key, metric_version, computation_version, eligibility_met);

-- !!! INTEGRATOR: reconcile with sibling migration 018 (event_classification) — 019 up must extend 018s body; 019 down must restore 018s body. This branch's down still restores 015 and MUST be reconciled by the merge lead.
-- INTEGRATION CAVEAT: migrations 016 and 017 only invoke this routine, so 015
-- owns the latest body in this branch.  Migration 018 is being built in a
-- sibling branch.  If 018 adds grant-managed tables, the integrator must merge
-- those additions into BOTH the up and down bodies below; applying this
-- 015-derived body unchanged after such an 018 would otherwise erase them.
-- program_rating joins the results-family SELECT+INSERT-only list.
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
      EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link, core.program_rating FROM pipeline_rw';
      EXECUTE 'GRANT SELECT, INSERT ON TABLE core.regatta, core.regatta_event, core.regatta_entry, core.regatta_result, core.provider_club, core.result_person, core.regatta_source_link, core.program_rating TO pipeline_rw';
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

DROP TABLE core.program_rating;
DELETE FROM core.metric_definition
WHERE metric_key = 'rating_rof' AND version = 1;

-- Restore the exact migration-015 body.  See the integration caveat above:
-- the merge owner must reconcile any grant changes introduced by sibling 018.
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
