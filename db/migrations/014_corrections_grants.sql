-- migrate:up

-- The public web role may submit corrections, but it must never be able to
-- read them back or change an existing submission.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_ro') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA app TO web_ro';
    EXECUTE 'REVOKE SELECT, UPDATE, DELETE, TRUNCATE ON TABLE app.correction_submission FROM web_ro';
    EXECUTE 'GRANT INSERT ON TABLE app.correction_submission TO web_ro';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_ro') THEN
    EXECUTE 'GRANT USAGE ON SCHEMA admin_v, app, read TO admin_ro';
    EXECUTE 'GRANT SELECT ON TABLE admin_v.review_task, admin_v.audit_event, app.correction_submission, read.org_directory TO admin_ro';
  END IF;
END;
$$;

-- migrate:down

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_ro') THEN
    EXECUTE 'REVOKE INSERT ON TABLE app.correction_submission FROM web_ro';
    EXECUTE 'REVOKE USAGE ON SCHEMA app FROM web_ro';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'admin_ro') THEN
    EXECUTE 'REVOKE SELECT ON TABLE admin_v.review_task, admin_v.audit_event, app.correction_submission, read.org_directory FROM admin_ro';
    EXECUTE 'REVOKE USAGE ON SCHEMA admin_v, app, read FROM admin_ro';
  END IF;
END;
$$;
