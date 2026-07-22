-- migrate:up

-- 002 shipped a generic legal-entity typology; the product taxonomy (PRD §7)
-- is rowing-native and drives directory filters and peer cohorts. Legal form
-- (c3/c7/for-profit) is derivable from BMF subsection codes, not a column.
ALTER TABLE core.organization ALTER COLUMN org_type DROP DEFAULT;
ALTER TYPE core.organization_type RENAME TO organization_type_legacy;
CREATE TYPE core.organization_type AS ENUM (
  'community_club',
  'private_membership_club',
  'scholastic_program',
  'collegiate_varsity',
  'collegiate_club',
  'university_support_foundation',
  'booster_club',
  'adaptive_program',
  'association',
  'governing_body',
  'other'
);
-- The taxonomies don't map onto each other; rows (none exist pre-cohort)
-- would coarsen to 'other'.
ALTER TABLE core.organization
  ALTER COLUMN org_type TYPE core.organization_type
  USING ('other'::core.organization_type);
ALTER TABLE core.organization ALTER COLUMN org_type SET DEFAULT 'other';
DROP TYPE core.organization_type_legacy;

-- migrate:down

ALTER TABLE core.organization ALTER COLUMN org_type DROP DEFAULT;
ALTER TYPE core.organization_type RENAME TO organization_type_rowing;
CREATE TYPE core.organization_type AS ENUM (
  'nonprofit',
  'for_profit',
  'government',
  'educational_institution',
  'unincorporated',
  'other'
);
ALTER TABLE core.organization
  ALTER COLUMN org_type TYPE core.organization_type
  USING ('other'::core.organization_type);
ALTER TABLE core.organization ALTER COLUMN org_type SET DEFAULT 'other';
DROP TYPE core.organization_type_rowing;
