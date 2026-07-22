-- migrate:up

CREATE TYPE core.source_type AS ENUM ('irs_bmf', 'irs_efile_index', 'irs_990_xml', 'irs_990n', 'propublica', 'givingtuesday');
CREATE TYPE core.filing_form_type AS ENUM ('990', '990EZ', '990N');
CREATE TYPE core.financial_fact_quality_state AS ENUM ('verified', 'partial', 'under_review');
CREATE TYPE core.metric_value_quality_state AS ENUM ('derived', 'partial', 'unavailable', 'under_review');
CREATE TYPE core.metric_definition_status AS ENUM ('draft', 'active', 'retired');

CREATE TABLE core.source_record (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source core.source_type NOT NULL,
  external_key text NOT NULL,
  checksum_sha256 text NOT NULL,
  raw_uri text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT source_record_source_external_checksum_uniq UNIQUE (source, external_key, checksum_sha256)
);
COMMENT ON TABLE core.source_record IS 'Immutable checksummed pointer to a raw source object.';

CREATE TABLE core.ein_observation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_record_id uuid NOT NULL,
  ein text NOT NULL,
  bmf_release_date date NOT NULL,
  legal_name text,
  city text,
  state text,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ein_observation_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT ein_observation_ein_bmf_release_date_uniq UNIQUE (ein, bmf_release_date),
  CONSTRAINT ein_observation_ein_format_check CHECK (ein ~ '^[0-9]{9}$')
);
COMMENT ON TABLE core.ein_observation IS 'Append-only BMF observations by release date.';
CREATE INDEX ein_observation_source_record_id_idx ON core.ein_observation (source_record_id);

CREATE TABLE core.epostcard_observation (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_record_id uuid NOT NULL,
  ein text NOT NULL,
  tax_year integer NOT NULL,
  tax_period_end date,
  filing_date date,
  raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT epostcard_observation_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT epostcard_observation_uniq UNIQUE (ein, tax_year, source_record_id),
  CONSTRAINT epostcard_observation_ein_format_check CHECK (ein ~ '^[0-9]{9}$')
);
COMMENT ON TABLE core.epostcard_observation IS '990-N presence only; it never supplies financial facts.';
CREATE INDEX epostcard_observation_source_record_id_idx ON core.epostcard_observation (source_record_id);
CREATE INDEX epostcard_observation_ein_tax_year_idx ON core.epostcard_observation (ein, tax_year);

CREATE TABLE core.filing (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid,
  source_record_id uuid,
  ein text NOT NULL,
  form_type core.filing_form_type NOT NULL,
  tax_period_begin date,
  tax_period_end date NOT NULL,
  tax_year integer NOT NULL,
  return_version text,
  irs_object_id text NOT NULL,
  amended_return boolean NOT NULL DEFAULT false,
  is_authoritative boolean NOT NULL DEFAULT false,
  superseded_by_filing_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT filing_organization_fk
    FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT filing_source_record_fk
    FOREIGN KEY (source_record_id) REFERENCES core.source_record(id),
  CONSTRAINT filing_superseded_by_filing_fk
    FOREIGN KEY (superseded_by_filing_id) REFERENCES core.filing(id),
  CONSTRAINT filing_ein_irs_object_id_uniq UNIQUE (ein, irs_object_id),
  CONSTRAINT filing_tax_period_check
    CHECK (tax_period_begin IS NULL OR tax_period_end >= tax_period_begin),
  CONSTRAINT filing_ein_format_check CHECK (ein ~ '^[0-9]{9}$')
);
COMMENT ON TABLE core.filing IS 'TaxYr is the comparison-alignment key; amended rows remain retained.';
CREATE INDEX filing_organization_id_idx ON core.filing (organization_id);
CREATE INDEX filing_source_record_id_idx ON core.filing (source_record_id);
CREATE INDEX filing_superseded_by_filing_id_idx ON core.filing (superseded_by_filing_id);
CREATE INDEX filing_ein_tax_period_end_idx ON core.filing (ein, tax_period_end);
CREATE INDEX filing_tax_year_idx ON core.filing (tax_year);

CREATE TABLE core.concept_definition (
  concept text PRIMARY KEY,
  label text NOT NULL,
  description text NOT NULL,
  unit text NOT NULL,
  available_990 boolean NOT NULL,
  available_990ez boolean NOT NULL,
  caveat text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT concept_definition_unit_check CHECK (unit IN ('USD', 'count'))
);

INSERT INTO core.concept_definition
  (concept, label, description, unit, available_990, available_990ez, caveat)
VALUES
  ('total_revenue', 'Total revenue', 'Total annual revenue.', 'USD', true, true, NULL),
  ('total_expenses', 'Total expenses', 'Total annual expenses.', 'USD', true, true, NULL),
  ('revenue_less_expenses', 'Revenue less expenses', 'Annual revenue less expenses.', 'USD', true, true, NULL),
  ('contributions_grants', 'Contributions and grants', 'Contributions and grants received.', 'USD', true, true, NULL),
  ('program_service_revenue', 'Program service revenue', 'Revenue from program services.', 'USD', true, true, NULL),
  ('membership_dues', 'Membership dues', 'Membership dues and assessments.', 'USD', true, true, NULL),
  ('investment_income', 'Investment income', 'Investment income.', 'USD', true, true, NULL),
  ('fundraising_events_gross', 'Fundraising events gross', 'Gross fundraising event revenue.', 'USD', true, true, NULL),
  ('fundraising_events_net', 'Fundraising events net', 'Net fundraising event revenue.', 'USD', true, true, NULL),
  ('other_revenue', 'Other revenue', 'Other revenue.', 'USD', true, true, NULL),
  ('grants_paid', 'Grants paid', 'Grants and similar amounts paid.', 'USD', true, true, NULL),
  ('salaries_benefits_total', 'Salaries and benefits', 'Total salaries, benefits, and payroll taxes.', 'USD', true, true, NULL),
  ('officer_compensation', 'Officer compensation', 'Compensation of current officers, directors, trustees, and key employees.', 'USD', true, true, NULL),
  ('professional_fundraising_fees', 'Professional fundraising fees', 'Fees for professional fundraising services.', 'USD', true, false, 'Unavailable on Form 990-EZ.'),
  ('occupancy', 'Occupancy', 'Occupancy expense.', 'USD', true, true, NULL),
  ('program_service_expense', 'Program service expense', 'Functional expense allocated to program services.', 'USD', true, false, 'Unavailable on Form 990-EZ.'),
  ('management_general_expense', 'Management and general expense', 'Functional expense allocated to management and general.', 'USD', true, false, 'Unavailable on Form 990-EZ.'),
  ('fundraising_expense', 'Fundraising expense', 'Functional expense allocated to fundraising.', 'USD', true, false, 'Unavailable on Form 990-EZ.'),
  ('total_assets_eoy', 'Total assets, end of year', 'Total assets at fiscal year end.', 'USD', true, true, NULL),
  ('total_liabilities_eoy', 'Total liabilities, end of year', 'Total liabilities at fiscal year end.', 'USD', true, true, NULL),
  ('net_assets_eoy', 'Net assets, end of year', 'Net assets or fund balances at fiscal year end.', 'USD', true, true, NULL),
  ('cash_savings_eoy', 'Cash and savings, end of year', 'Cash and savings at fiscal year end.', 'USD', true, true, 'On Form 990-EZ this can include investments (line 22).'),
  ('land_buildings_equipment_net', 'Land, buildings, and equipment, net', 'Net land, buildings, and equipment.', 'USD', true, true, NULL),
  ('employee_count', 'Employee count', 'Number of employees.', 'count', true, false, 'Unavailable on Form 990-EZ.');

CREATE TABLE core.financial_fact (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id uuid NOT NULL,
  concept text NOT NULL,
  normalization_version integer NOT NULL,
  amount numeric(16,2),
  source_path text NOT NULL,
  quality_state core.financial_fact_quality_state NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT financial_fact_filing_fk
    FOREIGN KEY (filing_id) REFERENCES core.filing(id),
  CONSTRAINT financial_fact_concept_fk
    FOREIGN KEY (concept) REFERENCES core.concept_definition(concept),
  CONSTRAINT financial_fact_filing_concept_version_uniq
    UNIQUE (filing_id, concept, normalization_version)
);
COMMENT ON TABLE core.financial_fact IS 'Exact extracted source paths; reparsing creates a new normalization version.';
CREATE INDEX financial_fact_filing_id_idx ON core.financial_fact (filing_id);
CREATE INDEX financial_fact_concept_idx ON core.financial_fact (concept);

CREATE TABLE core.person_role (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filing_id uuid NOT NULL,
  person_name text NOT NULL,
  title text,
  reportable_compensation numeric(16,2),
  other_compensation numeric(16,2),
  deferred_compensation numeric(16,2),
  nontaxable_benefits numeric(16,2),
  related_organization_compensation numeric(16,2),
  role_flags text[] NOT NULL DEFAULT ARRAY[]::text[],
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT person_role_filing_fk
    FOREIGN KEY (filing_id) REFERENCES core.filing(id)
);
COMMENT ON TABLE core.person_role IS 'Filing-scoped roles only; no cross-organization person graph is implied.';
CREATE INDEX person_role_filing_id_idx ON core.person_role (filing_id);

CREATE TABLE core.metric_definition (
  metric_key text NOT NULL,
  version integer NOT NULL,
  label text NOT NULL,
  description text NOT NULL,
  unit text NOT NULL,
  eligibility_rule jsonb NOT NULL,
  limitation text,
  status core.metric_definition_status NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (metric_key, version)
);

CREATE TABLE core.metric_value (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_key text NOT NULL,
  metric_version integer NOT NULL,
  organization_id uuid NOT NULL,
  tax_year integer NOT NULL,
  fiscal_year_end date NOT NULL,
  value numeric(16,2),
  quality_state core.metric_value_quality_state NOT NULL,
  input_fact_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT metric_value_metric_definition_fk
    FOREIGN KEY (metric_key, metric_version)
    REFERENCES core.metric_definition(metric_key, version),
  CONSTRAINT metric_value_organization_fk
    FOREIGN KEY (organization_id) REFERENCES core.organization(id),
  CONSTRAINT metric_value_metric_org_fye_uniq
    UNIQUE (metric_key, metric_version, organization_id, fiscal_year_end)
);
CREATE INDEX metric_value_metric_definition_idx ON core.metric_value (metric_key, metric_version);
CREATE INDEX metric_value_organization_id_idx ON core.metric_value (organization_id);
CREATE INDEX metric_value_tax_year_idx ON core.metric_value (tax_year);

-- migrate:down

DROP TABLE core.metric_value;
DROP TABLE core.metric_definition;
DROP TABLE core.person_role;
DROP TABLE core.financial_fact;
DROP TABLE core.concept_definition;
DROP TABLE core.filing;
DROP TABLE core.epostcard_observation;
DROP TABLE core.ein_observation;
DROP TABLE core.source_record;
DROP TYPE core.metric_definition_status;
DROP TYPE core.metric_value_quality_state;
DROP TYPE core.financial_fact_quality_state;
DROP TYPE core.filing_form_type;
DROP TYPE core.source_type;
