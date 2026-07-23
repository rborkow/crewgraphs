-- migrate:up

CREATE TABLE read.org_regatta_result (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id uuid NOT NULL REFERENCES ops.publish_snapshot(id),
  organization_id uuid NOT NULL REFERENCES core.organization(id),
  season integer NOT NULL,
  regatta_key text NOT NULL,
  regatta_name text NOT NULL,
  regatta_date date,
  venue text,
  source_key text NOT NULL,
  event_key text NOT NULL,
  entry_external_key text NOT NULL,
  event_name text NOT NULL,
  boat_class text,
  round text,
  crew_label text,
  crew jsonb NOT NULL DEFAULT '[]'::jsonb,
  metric_key text NOT NULL CHECK (
    metric_key IN (
      'finish_time',
      'adjusted_time',
      'handicap',
      'place',
      'adjusted_place',
      'margin'
    )
  ),
  value numeric,
  unit text NOT NULL,
  status text NOT NULL,
  quality_state text NOT NULL,
  source_ref jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE read.org_regatta_result IS
  'Snapshot-scoped long-form regatta results. crew contains only post-suppression race-context names.';
CREATE INDEX org_regatta_result_snapshot_organization_idx
  ON read.org_regatta_result (snapshot_id, organization_id);
CREATE INDEX org_regatta_result_snapshot_organization_season_idx
  ON read.org_regatta_result (snapshot_id, organization_id, season);
CREATE UNIQUE INDEX org_regatta_result_snapshot_metric_uniq
  ON read.org_regatta_result (
    snapshot_id,
    organization_id,
    regatta_key,
    event_key,
    entry_external_key,
    COALESCE(crew_label, ''),
    metric_key
  );

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

DROP TABLE read.org_regatta_result;
