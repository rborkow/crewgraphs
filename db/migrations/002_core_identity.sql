-- migrate:up

CREATE TYPE core.organization_type AS ENUM (
  'nonprofit', 'for_profit', 'government', 'educational_institution', 'unincorporated', 'other'
);
CREATE TYPE core.organization_status AS ENUM ('candidate', 'included', 'excluded', 'merged');
CREATE TYPE core.identifier_namespace AS ENUM (
  'irs_ein', 'propublica_ein', 'website_domain', 'usrowing', 'regattacentral_org'
);
CREATE TYPE core.relationship_type AS ENUM (
  'program_of', 'fiscally_sponsored_by', 'successor_of', 'supports', 'boosters_for',
  'shares_boathouse_with', 'has_charitable_arm', 'affiliated_forprofit'
);

CREATE TABLE core.organization (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  display_name text NOT NULL,
  legal_name text,
  org_type core.organization_type NOT NULL DEFAULT 'other',
  status core.organization_status NOT NULL DEFAULT 'candidate',
  merged_into_id uuid,
  city text,
  state text,
  metro_area text,
  website text,
  founded_year integer,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT organization_merged_into_fk
    FOREIGN KEY (merged_into_id) REFERENCES core.organization(id),
  CONSTRAINT organization_founded_year_check
    CHECK (founded_year IS NULL OR founded_year BETWEEN 1600 AND 9999)
);
CREATE INDEX organization_merged_into_id_idx ON core.organization (merged_into_id);

CREATE TABLE core.external_identifier (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  namespace core.identifier_namespace NOT NULL,
  value text NOT NULL,
  verification_state text NOT NULL DEFAULT 'unverified',
  valid_from date,
  valid_to date,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT external_identifier_organization_fk
    FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT external_identifier_valid_range_check
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  CONSTRAINT external_identifier_verification_state_check
    CHECK (verification_state IN ('unverified', 'verified', 'rejected'))
);
CREATE INDEX external_identifier_organization_id_idx ON core.external_identifier (organization_id);
CREATE UNIQUE INDEX external_identifier_verified_active_uniq
  ON core.external_identifier (namespace, value)
  WHERE valid_to IS NULL AND verification_state = 'verified';

CREATE TABLE core.organization_alias (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  alias text NOT NULL,
  alias_normalized text GENERATED ALWAYS AS (
    lower(regexp_replace(alias, '[[:punct:]]', '', 'g'))
  ) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT organization_alias_organization_fk
    FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT organization_alias_organization_alias_uniq UNIQUE (organization_id, alias)
);
CREATE INDEX organization_alias_organization_id_idx ON core.organization_alias (organization_id);
CREATE INDEX organization_alias_normalized_idx ON core.organization_alias (alias_normalized);

CREATE TABLE core.organization_relationship (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_organization_id uuid NOT NULL,
  to_organization_id uuid NOT NULL,
  relationship_type core.relationship_type NOT NULL,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT organization_relationship_from_organization_fk
    FOREIGN KEY (from_organization_id) REFERENCES core.organization(id),
  CONSTRAINT organization_relationship_to_organization_fk
    FOREIGN KEY (to_organization_id) REFERENCES core.organization(id),
  CONSTRAINT organization_relationship_distinct_orgs_check
    CHECK (from_organization_id <> to_organization_id),
  CONSTRAINT organization_relationship_uniq
    UNIQUE (from_organization_id, to_organization_id, relationship_type)
);
CREATE INDEX organization_relationship_from_organization_id_idx
  ON core.organization_relationship (from_organization_id);
CREATE INDEX organization_relationship_to_organization_id_idx
  ON core.organization_relationship (to_organization_id);

CREATE TABLE core.review_task (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  task_type text NOT NULL,
  status text NOT NULL DEFAULT 'open',
  assigned_to text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT review_task_status_check CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed'))
);
CREATE INDEX review_task_entity_idx ON core.review_task (entity_type, entity_id);
CREATE INDEX review_task_status_idx ON core.review_task (status);

CREATE TABLE core.audit_event (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor text NOT NULL,
  action text NOT NULL,
  entity_type text NOT NULL,
  entity_id uuid NOT NULL,
  before jsonb,
  after jsonb,
  reversal_of_event_id uuid,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT audit_event_reversal_of_event_fk
    FOREIGN KEY (reversal_of_event_id) REFERENCES core.audit_event(id)
);
CREATE INDEX audit_event_entity_idx ON core.audit_event (entity_type, entity_id);
CREATE INDEX audit_event_reversal_of_event_id_idx ON core.audit_event (reversal_of_event_id);
CREATE INDEX audit_event_occurred_at_idx ON core.audit_event (occurred_at);

-- migrate:down

DROP TABLE core.audit_event;
DROP TABLE core.review_task;
DROP TABLE core.organization_relationship;
DROP TABLE core.organization_alias;
DROP TABLE core.external_identifier;
DROP TABLE core.organization;
DROP TYPE core.relationship_type;
DROP TYPE core.identifier_namespace;
DROP TYPE core.organization_status;
DROP TYPE core.organization_type;
