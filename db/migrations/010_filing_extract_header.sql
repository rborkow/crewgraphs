-- migrate:up

-- The extractor captures the return header, but 004's filing_extract had
-- nowhere to put it — cross_check needs tax_period_end to align with
-- ProPublica tax_prd, and derive needs form_type/return_version/amended.
ALTER TABLE staging.filing_extract ADD COLUMN form_type text;
ALTER TABLE staging.filing_extract ADD COLUMN return_version text;
ALTER TABLE staging.filing_extract ADD COLUMN tax_period_begin date;
ALTER TABLE staging.filing_extract ADD COLUMN tax_period_end date;
ALTER TABLE staging.filing_extract ADD COLUMN amended_return boolean DEFAULT false NOT NULL;

-- migrate:down

ALTER TABLE staging.filing_extract DROP COLUMN amended_return;
ALTER TABLE staging.filing_extract DROP COLUMN tax_period_end;
ALTER TABLE staging.filing_extract DROP COLUMN tax_period_begin;
ALTER TABLE staging.filing_extract DROP COLUMN return_version;
ALTER TABLE staging.filing_extract DROP COLUMN form_type;
