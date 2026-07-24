-- migrate:up

CREATE TABLE staging.regattatiming_page (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingest_run_id uuid REFERENCES ops.ingest_run(id),
  source_record_id uuid NOT NULL REFERENCES core.source_record(id),
  race_id integer NOT NULL UNIQUE,
  page_kind text NOT NULL CHECK (page_kind IN ('summary', 'static')),
  title text,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX regattatiming_page_ingest_run_id_idx
  ON staging.regattatiming_page (ingest_run_id);

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

DROP TABLE staging.regattatiming_page;
