-- migrate:up

-- Acquisition jobs need real idempotency targets: 004 shipped these staging
-- tables without natural-key uniqueness, forcing NOT-EXISTS guards and
-- update-then-insert workarounds. IRS object ids are globally unique; the
-- propublica staging row holds the latest payload per EIN.
CREATE UNIQUE INDEX efile_index_row_object_uq ON staging.efile_index_row (irs_object_id);
CREATE UNIQUE INDEX filing_extract_object_uq ON staging.filing_extract (irs_object_id);
CREATE UNIQUE INDEX propublica_org_ein_uq ON staging.propublica_org (ein);

-- migrate:down

DROP INDEX staging.propublica_org_ein_uq;
DROP INDEX staging.filing_extract_object_uq;
DROP INDEX staging.efile_index_row_object_uq;
