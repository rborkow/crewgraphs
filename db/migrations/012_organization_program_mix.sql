-- migrate:up

-- 002 dropped the spec's program_mix multi-select (PRD §7 taxonomy). It is
-- required by the contracts directory/profile schemas and drives directory
-- filters; seed cohort carries it as pipe-separated values.
ALTER TABLE core.organization ADD COLUMN program_mix text[] NOT NULL DEFAULT '{}';

-- migrate:down

ALTER TABLE core.organization DROP COLUMN program_mix;
