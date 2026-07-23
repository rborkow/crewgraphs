\restrict dbmate

-- Dumped from database version 18.4 (Debian 18.4-1.pgdg13+1)
-- Dumped by pg_dump version 18.4 (Debian 18.4-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: admin_v; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA admin_v;


--
-- Name: app; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA app;


--
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA core;


--
-- Name: ops; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA ops;


--
-- Name: read; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA read;


--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA staging;


--
-- Name: filing_form_type; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.filing_form_type AS ENUM (
    '990',
    '990EZ',
    '990N'
);


--
-- Name: financial_fact_quality_state; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.financial_fact_quality_state AS ENUM (
    'verified',
    'partial',
    'under_review'
);


--
-- Name: identifier_namespace; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.identifier_namespace AS ENUM (
    'irs_ein',
    'propublica_ein',
    'website_domain',
    'usrowing',
    'regattacentral_org',
    'time_team_club'
);


--
-- Name: metric_definition_status; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.metric_definition_status AS ENUM (
    'draft',
    'active',
    'retired'
);


--
-- Name: metric_value_quality_state; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.metric_value_quality_state AS ENUM (
    'derived',
    'partial',
    'unavailable',
    'under_review'
);


--
-- Name: organization_status; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.organization_status AS ENUM (
    'candidate',
    'included',
    'excluded',
    'merged'
);


--
-- Name: organization_type; Type: TYPE; Schema: core; Owner: -
--

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


--
-- Name: relationship_type; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.relationship_type AS ENUM (
    'program_of',
    'fiscally_sponsored_by',
    'successor_of',
    'supports',
    'boosters_for',
    'shares_boathouse_with',
    'has_charitable_arm',
    'affiliated_forprofit'
);


--
-- Name: source_type; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.source_type AS ENUM (
    'irs_bmf',
    'irs_efile_index',
    'irs_990_xml',
    'irs_990n',
    'propublica',
    'givingtuesday',
    'herenow',
    'time_team',
    'row2k',
    'regattatiming',
    'crewtimer'
);


--
-- Name: ingest_run_status; Type: TYPE; Schema: ops; Owner: -
--

CREATE TYPE ops.ingest_run_status AS ENUM (
    'running',
    'succeeded',
    'failed',
    'partial'
);


--
-- Name: publish_snapshot_status; Type: TYPE; Schema: ops; Owner: -
--

CREATE TYPE ops.publish_snapshot_status AS ENUM (
    'building',
    'active',
    'superseded',
    'rolled_back'
);


--
-- Name: coverage_state; Type: TYPE; Schema: read; Owner: -
--

CREATE TYPE read.coverage_state AS ENUM (
    '990',
    '990ez',
    '990n_only',
    'none'
);


--
-- Name: filing_coverage_status; Type: TYPE; Schema: read; Owner: -
--

CREATE TYPE read.filing_coverage_status AS ENUM (
    '990',
    '990ez',
    '990n',
    'amended',
    'missing',
    'not_yet_expected'
);


--
-- Name: series_quality_state; Type: TYPE; Schema: read; Owner: -
--

CREATE TYPE read.series_quality_state AS ENUM (
    'verified',
    'derived',
    'partial',
    'unavailable',
    'under_review'
);


--
-- Name: apply_phase1_role_grants(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.apply_phase1_role_grants() RETURNS void
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


--
-- Name: apply_phase2_pipeline_grants(); Type: FUNCTION; Schema: app; Owner: -
--

CREATE FUNCTION app.apply_phase2_pipeline_grants() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pipeline_rw') THEN
    EXECUTE 'GRANT SELECT, INSERT ON TABLE core.review_task, core.audit_event TO pipeline_rw';
    EXECUTE 'REVOKE UPDATE, DELETE, TRUNCATE ON TABLE core.review_task, core.audit_event FROM pipeline_rw';
    -- resolve reads identity tables to find verified EINs; reading is safe.
    EXECUTE 'GRANT SELECT ON TABLE core.organization, core.external_identifier, core.organization_alias, core.organization_relationship TO pipeline_rw';
    EXECUTE 'GRANT SELECT ON TABLE core.concept_definition, core.metric_definition TO pipeline_rw';
  END IF;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_event; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.audit_event (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    before jsonb,
    after jsonb,
    reversal_of_event_id uuid,
    occurred_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: audit_event; Type: VIEW; Schema: admin_v; Owner: -
--

CREATE VIEW admin_v.audit_event AS
 SELECT id,
    actor,
    action,
    entity_type,
    entity_id,
    before,
    after,
    reversal_of_event_id,
    occurred_at,
    created_at
   FROM core.audit_event;


--
-- Name: review_task; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.review_task (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    task_type text NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    assigned_to text,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT review_task_status_check CHECK ((status = ANY (ARRAY['open'::text, 'in_progress'::text, 'resolved'::text, 'dismissed'::text])))
);


--
-- Name: review_task; Type: VIEW; Schema: admin_v; Owner: -
--

CREATE VIEW admin_v.review_task AS
 SELECT id,
    entity_type,
    entity_id,
    task_type,
    status,
    assigned_to,
    details,
    created_at
   FROM core.review_task;


--
-- Name: correction_submission; Type: TABLE; Schema: app; Owner: -
--

CREATE TABLE app.correction_submission (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid,
    submitter_email text,
    message text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT correction_submission_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'reviewed'::text, 'resolved'::text, 'rejected'::text])))
);


--
-- Name: concept_definition; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.concept_definition (
    concept text NOT NULL,
    label text NOT NULL,
    description text NOT NULL,
    unit text NOT NULL,
    available_990 boolean NOT NULL,
    available_990ez boolean NOT NULL,
    caveat text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT concept_definition_unit_check CHECK ((unit = ANY (ARRAY['USD'::text, 'count'::text])))
);


--
-- Name: ein_observation; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.ein_observation (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_record_id uuid NOT NULL,
    ein text NOT NULL,
    bmf_release_date date NOT NULL,
    legal_name text,
    city text,
    state text,
    raw_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ein_observation_ein_format_check CHECK ((ein ~ '^[0-9]{9}$'::text))
);


--
-- Name: TABLE ein_observation; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.ein_observation IS 'Append-only BMF observations by release date.';


--
-- Name: epostcard_observation; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.epostcard_observation (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source_record_id uuid NOT NULL,
    ein text NOT NULL,
    tax_year integer NOT NULL,
    tax_period_end date,
    filing_date date,
    raw_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT epostcard_observation_ein_format_check CHECK ((ein ~ '^[0-9]{9}$'::text))
);


--
-- Name: TABLE epostcard_observation; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.epostcard_observation IS '990-N presence only; it never supplies financial facts.';


--
-- Name: external_identifier; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.external_identifier (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    namespace core.identifier_namespace NOT NULL,
    value text NOT NULL,
    verification_state text DEFAULT 'unverified'::text NOT NULL,
    valid_from date,
    valid_to date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT external_identifier_valid_range_check CHECK (((valid_to IS NULL) OR (valid_from IS NULL) OR (valid_to >= valid_from))),
    CONSTRAINT external_identifier_verification_state_check CHECK ((verification_state = ANY (ARRAY['unverified'::text, 'verified'::text, 'rejected'::text])))
);


--
-- Name: filing; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.filing (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid,
    source_record_id uuid,
    ein text NOT NULL,
    form_type core.filing_form_type NOT NULL,
    tax_period_begin date,
    tax_period_end date NOT NULL,
    tax_year integer NOT NULL,
    return_version text,
    irs_object_id text NOT NULL,
    amended_return boolean DEFAULT false NOT NULL,
    is_authoritative boolean DEFAULT false NOT NULL,
    superseded_by_filing_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT filing_ein_format_check CHECK ((ein ~ '^[0-9]{9}$'::text)),
    CONSTRAINT filing_tax_period_check CHECK (((tax_period_begin IS NULL) OR (tax_period_end >= tax_period_begin)))
);


--
-- Name: TABLE filing; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.filing IS 'TaxYr is the comparison-alignment key; amended rows remain retained.';


--
-- Name: financial_fact; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.financial_fact (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    filing_id uuid NOT NULL,
    concept text NOT NULL,
    normalization_version integer NOT NULL,
    amount numeric(16,2),
    source_path text NOT NULL,
    quality_state core.financial_fact_quality_state NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE financial_fact; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.financial_fact IS 'Exact extracted source paths; reparsing creates a new normalization version.';


--
-- Name: metric_definition; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.metric_definition (
    metric_key text NOT NULL,
    version integer NOT NULL,
    label text NOT NULL,
    description text NOT NULL,
    unit text NOT NULL,
    eligibility_rule jsonb NOT NULL,
    limitation text,
    status core.metric_definition_status DEFAULT 'draft'::core.metric_definition_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: metric_value; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.metric_value (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    metric_key text NOT NULL,
    metric_version integer NOT NULL,
    organization_id uuid NOT NULL,
    tax_year integer NOT NULL,
    fiscal_year_end date NOT NULL,
    value numeric(16,2),
    quality_state core.metric_value_quality_state NOT NULL,
    input_fact_ids uuid[] DEFAULT ARRAY[]::uuid[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organization; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.organization (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    slug text NOT NULL,
    display_name text NOT NULL,
    legal_name text,
    org_type core.organization_type DEFAULT 'other'::core.organization_type NOT NULL,
    status core.organization_status DEFAULT 'candidate'::core.organization_status NOT NULL,
    merged_into_id uuid,
    city text,
    state text,
    metro_area text,
    website text,
    founded_year integer,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    program_mix text[] DEFAULT '{}'::text[] NOT NULL,
    CONSTRAINT organization_founded_year_check CHECK (((founded_year IS NULL) OR ((founded_year >= 1600) AND (founded_year <= 9999))))
);


--
-- Name: organization_alias; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.organization_alias (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    organization_id uuid NOT NULL,
    alias text NOT NULL,
    alias_normalized text GENERATED ALWAYS AS (lower(regexp_replace(alias, '[[:punct:]]'::text, ''::text, 'g'::text))) STORED,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: organization_relationship; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.organization_relationship (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    from_organization_id uuid NOT NULL,
    to_organization_id uuid NOT NULL,
    relationship_type core.relationship_type NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT organization_relationship_distinct_orgs_check CHECK ((from_organization_id <> to_organization_id))
);


--
-- Name: person_role; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.person_role (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    filing_id uuid NOT NULL,
    person_name text NOT NULL,
    title text,
    reportable_compensation numeric(16,2),
    other_compensation numeric(16,2),
    deferred_compensation numeric(16,2),
    nontaxable_benefits numeric(16,2),
    related_organization_compensation numeric(16,2),
    role_flags text[] DEFAULT ARRAY[]::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    avg_hours_week numeric(5,2)
);


--
-- Name: TABLE person_role; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.person_role IS 'Filing-scoped roles only; no cross-organization person graph is implied.';


--
-- Name: person_suppression; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.person_suppression (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    person_name_normalized text NOT NULL,
    source core.source_type,
    provider_club_id uuid,
    reason text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE person_suppression; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.person_suppression IS 'Curator-only takedown list; publish redacts matching names (optionally scoped to a source/club). NULL scope = global.';


--
-- Name: provider_club; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.provider_club (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source core.source_type NOT NULL,
    external_key text NOT NULL,
    display_name text NOT NULL,
    code text,
    federation text,
    raw jsonb DEFAULT '{}'::jsonb NOT NULL,
    source_record_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE provider_club; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.provider_club IS 'Provider-side club observation. The org link lives only in curator-owned core.external_identifier (namespace time_team_club) or organization_alias.';


--
-- Name: regatta; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.regatta (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source core.source_type NOT NULL,
    external_key text NOT NULL,
    revision integer DEFAULT 1 NOT NULL,
    name text NOT NULL,
    start_date date,
    end_date date,
    venue text,
    city text,
    state text,
    category text,
    raw jsonb DEFAULT '{}'::jsonb NOT NULL,
    payload_checksum text NOT NULL,
    source_record_id uuid,
    parser_version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT regatta_date_range_check CHECK (((end_date IS NULL) OR (start_date IS NULL) OR (end_date >= start_date)))
);


--
-- Name: TABLE regatta; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.regatta IS 'One provider regatta payload capture; payload_checksum makes an unchanged re-load a no-op instead of a new revision.';


--
-- Name: regatta_entry; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.regatta_entry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id uuid NOT NULL,
    external_key text NOT NULL,
    bib text,
    lane integer,
    club_source_name text NOT NULL,
    provider_club_id uuid,
    crew_label text,
    raw jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE regatta_entry; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.regatta_entry IS 'club_source_name keeps the provider string verbatim even once provider_club resolves. Person names live only in core.result_person.';


--
-- Name: regatta_event; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.regatta_event (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    regatta_id uuid NOT NULL,
    external_key text NOT NULL,
    name text NOT NULL,
    event_code text,
    boat_class_raw text,
    age_class_raw text,
    gender_raw text,
    round text,
    scheduled_at timestamp with time zone,
    progression jsonb DEFAULT '[]'::jsonb NOT NULL,
    raw jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE regatta_event; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.regatta_event IS 'Provider-raw classification only; canonical boat class / age bracket / gender land in the versioned event_classification table (Wave 3).';


--
-- Name: regatta_result; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.regatta_result (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entry_id uuid NOT NULL,
    status text NOT NULL,
    "position" integer,
    adjusted_position integer,
    time_ms bigint,
    adjusted_time_ms bigint,
    handicap_ms bigint,
    delta_ms bigint,
    penalty jsonb,
    correction jsonb,
    splits jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT regatta_result_time_sanity_check CHECK (((time_ms IS NULL) OR (time_ms > 0)))
);


--
-- Name: TABLE regatta_result; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.regatta_result IS 'status keeps the provider vocabulary raw (DNS/DNF/DSQ/withdrawn/relegated/OOC…); normalization is a publish concern.';


--
-- Name: regatta_source_link; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.regatta_source_link (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    regatta_name text NOT NULL,
    event_date date,
    category text,
    location text,
    outbound_url text NOT NULL,
    outbound_host text NOT NULL,
    provider core.source_type,
    credit_url text NOT NULL,
    source_record_id uuid,
    retrieved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE regatta_source_link; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.regatta_source_link IS 'row2k discovery facts and outbound links only; never result content, per row2k link-don''t-copy policy.';


--
-- Name: result_person; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.result_person (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    entry_id uuid NOT NULL,
    role text NOT NULL,
    seat integer,
    person_name text NOT NULL,
    raw jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE result_person; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.result_person IS 'The only person-level store for results (PII policy 2026-07-23). FK points at the entry so this table is purgeable without touching results.';


--
-- Name: source_record; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.source_record (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    source core.source_type NOT NULL,
    external_key text NOT NULL,
    checksum_sha256 text NOT NULL,
    raw_uri text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE source_record; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.source_record IS 'Immutable checksummed pointer to a raw source object.';


--
-- Name: ingest_run; Type: TABLE; Schema: ops; Owner: -
--

CREATE TABLE ops.ingest_run (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    job_name text NOT NULL,
    git_sha text NOT NULL,
    code_version text NOT NULL,
    params jsonb DEFAULT '{}'::jsonb NOT NULL,
    stats jsonb DEFAULT '{}'::jsonb NOT NULL,
    status ops.ingest_run_status DEFAULT 'running'::ops.ingest_run_status NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    source text,
    error text,
    CONSTRAINT ingest_run_finished_at_check CHECK (((finished_at IS NULL) OR (finished_at >= started_at)))
);


--
-- Name: publish_snapshot; Type: TABLE; Schema: ops; Owner: -
--

CREATE TABLE ops.publish_snapshot (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    status ops.publish_snapshot_status DEFAULT 'building'::ops.publish_snapshot_status NOT NULL,
    manifest jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    activated_at timestamp with time zone
);


--
-- Name: quarantine; Type: TABLE; Schema: ops; Owner: -
--

CREATE TABLE ops.quarantine (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    reason text NOT NULL,
    raw_uri text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb NOT NULL,
    resolved boolean DEFAULT false NOT NULL,
    resolved_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT quarantine_resolved_at_check CHECK (((NOT resolved) OR (resolved_at IS NOT NULL)))
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: metric_catalog; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.metric_catalog (
    snapshot_id uuid NOT NULL,
    metric_key text NOT NULL,
    metric_version integer NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: org_directory; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_directory (
    snapshot_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    slug text NOT NULL,
    display_name text NOT NULL,
    coverage_state read.coverage_state NOT NULL,
    aliases jsonb DEFAULT '[]'::jsonb NOT NULL,
    search_text tsvector DEFAULT ''::tsvector NOT NULL,
    fye_month integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT org_directory_fye_month_check CHECK ((((fye_month >= 1) AND (fye_month <= 12)) OR (fye_month IS NULL)))
);


--
-- Name: org_filing_coverage; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_filing_coverage (
    snapshot_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    tax_year integer NOT NULL,
    status read.filing_coverage_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: org_financial_series; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_financial_series (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    snapshot_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    series_key text NOT NULL,
    series_version integer NOT NULL,
    tax_year integer NOT NULL,
    fiscal_year_end date NOT NULL,
    value numeric(16,2),
    quality_state read.series_quality_state NOT NULL,
    is_amended boolean DEFAULT false NOT NULL,
    source_ref jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE org_financial_series; Type: COMMENT; Schema: read; Owner: -
--

COMMENT ON TABLE read.org_financial_series IS 'Long-form values; source_ref accommodates the contracts SourceRef provenance object.';


--
-- Name: org_peer_cohort; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_peer_cohort (
    snapshot_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    cohort_key text NOT NULL,
    reason_labels jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: org_profile; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_profile (
    snapshot_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    payload jsonb NOT NULL,
    payload_schema_version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE org_profile; Type: COMMENT; Schema: read; Owner: -
--

COMMENT ON TABLE read.org_profile IS 'Versioned public profile payload.';


--
-- Name: org_slug_history; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.org_slug_history (
    slug text NOT NULL,
    snapshot_id uuid NOT NULL,
    org_id uuid NOT NULL,
    is_current boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE org_slug_history; Type: COMMENT; Schema: read; Owner: -
--

COMMENT ON TABLE read.org_slug_history IS 'Slugs are globally unique and never reused.';


--
-- Name: published_snapshot; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.published_snapshot (
    singleton boolean DEFAULT true NOT NULL,
    snapshot_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT published_snapshot_singleton_check CHECK (singleton)
);


--
-- Name: TABLE published_snapshot; Type: COMMENT; Schema: read; Owner: -
--

COMMENT ON TABLE read.published_snapshot IS 'Single-row pointer atomically selecting the public read-model snapshot.';


--
-- Name: source_registry_public; Type: TABLE; Schema: read; Owner: -
--

CREATE TABLE read.source_registry_public (
    snapshot_id uuid NOT NULL,
    source_key text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: bmf_row; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.bmf_row (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    bmf_release_date date NOT NULL,
    ein text,
    raw_row jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE bmf_row; Type: COMMENT; Schema: staging; Owner: -
--

COMMENT ON TABLE staging.bmf_row IS 'Unnormalized row from one BMF release.';


--
-- Name: efile_index_row; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.efile_index_row (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    tax_year integer NOT NULL,
    ein text,
    irs_object_id text NOT NULL,
    xml_batch_id text NOT NULL,
    raw_row jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE efile_index_row; Type: COMMENT; Schema: staging; Owner: -
--

COMMENT ON TABLE staging.efile_index_row IS 'IRS index row retaining the XML batch identifier for fallback fetches.';


--
-- Name: epostcard_row; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.epostcard_row (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    ein text,
    raw_row jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: filing_extract; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.filing_extract (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid NOT NULL,
    ein text NOT NULL,
    irs_object_id text NOT NULL,
    concepts jsonb DEFAULT '{}'::jsonb NOT NULL,
    people jsonb DEFAULT '[]'::jsonb NOT NULL,
    warnings jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    form_type text,
    return_version text,
    tax_period_begin date,
    tax_period_end date,
    amended_return boolean DEFAULT false NOT NULL
);


--
-- Name: herenow_catalog_row; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.herenow_catalog_row (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    race_id bigint NOT NULL,
    raw_row jsonb NOT NULL,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: herenow_race_payload; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.herenow_race_payload (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    race_id bigint NOT NULL,
    kind text NOT NULL,
    raw_payload jsonb NOT NULL,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT herenow_race_payload_kind_check CHECK ((kind = ANY (ARRAY['base'::text, 'flights'::text])))
);


--
-- Name: propublica_org; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.propublica_org (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    ein text NOT NULL,
    raw_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: regattatiming_page; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.regattatiming_page (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid NOT NULL,
    race_id integer NOT NULL,
    page_kind text NOT NULL,
    title text,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT regattatiming_page_page_kind_check CHECK ((page_kind = ANY (ARRAY['summary'::text, 'static'::text])))
);


--
-- Name: row2k_index_page; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.row2k_index_page (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    year integer NOT NULL,
    category text,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: time_team_race; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.time_team_race (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    slug text NOT NULL,
    year integer NOT NULL,
    race_uuid uuid NOT NULL,
    raw_payload jsonb NOT NULL,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: time_team_regatta; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.time_team_regatta (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    ingest_run_id uuid,
    source_record_id uuid,
    slug text NOT NULL,
    year integer NOT NULL,
    raw_payload jsonb,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE time_team_regatta; Type: COMMENT; Schema: staging; Owner: -
--

COMMENT ON TABLE staging.time_team_regatta IS 'raw_payload is NULL between index discovery and race-sync fetching the schedule doc.';


--
-- Name: correction_submission correction_submission_pkey; Type: CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.correction_submission
    ADD CONSTRAINT correction_submission_pkey PRIMARY KEY (id);


--
-- Name: audit_event audit_event_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.audit_event
    ADD CONSTRAINT audit_event_pkey PRIMARY KEY (id);


--
-- Name: concept_definition concept_definition_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.concept_definition
    ADD CONSTRAINT concept_definition_pkey PRIMARY KEY (concept);


--
-- Name: ein_observation ein_observation_ein_bmf_release_date_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.ein_observation
    ADD CONSTRAINT ein_observation_ein_bmf_release_date_uniq UNIQUE (ein, bmf_release_date);


--
-- Name: ein_observation ein_observation_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.ein_observation
    ADD CONSTRAINT ein_observation_pkey PRIMARY KEY (id);


--
-- Name: epostcard_observation epostcard_observation_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.epostcard_observation
    ADD CONSTRAINT epostcard_observation_pkey PRIMARY KEY (id);


--
-- Name: epostcard_observation epostcard_observation_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.epostcard_observation
    ADD CONSTRAINT epostcard_observation_uniq UNIQUE (ein, tax_year, source_record_id);


--
-- Name: external_identifier external_identifier_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.external_identifier
    ADD CONSTRAINT external_identifier_pkey PRIMARY KEY (id);


--
-- Name: filing filing_ein_irs_object_id_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.filing
    ADD CONSTRAINT filing_ein_irs_object_id_uniq UNIQUE (ein, irs_object_id);


--
-- Name: filing filing_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.filing
    ADD CONSTRAINT filing_pkey PRIMARY KEY (id);


--
-- Name: financial_fact financial_fact_filing_concept_version_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.financial_fact
    ADD CONSTRAINT financial_fact_filing_concept_version_uniq UNIQUE (filing_id, concept, normalization_version);


--
-- Name: financial_fact financial_fact_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.financial_fact
    ADD CONSTRAINT financial_fact_pkey PRIMARY KEY (id);


--
-- Name: metric_definition metric_definition_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.metric_definition
    ADD CONSTRAINT metric_definition_pkey PRIMARY KEY (metric_key, version);


--
-- Name: metric_value metric_value_metric_org_fye_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.metric_value
    ADD CONSTRAINT metric_value_metric_org_fye_uniq UNIQUE (metric_key, metric_version, organization_id, fiscal_year_end);


--
-- Name: metric_value metric_value_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.metric_value
    ADD CONSTRAINT metric_value_pkey PRIMARY KEY (id);


--
-- Name: organization_alias organization_alias_organization_alias_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_alias
    ADD CONSTRAINT organization_alias_organization_alias_uniq UNIQUE (organization_id, alias);


--
-- Name: organization_alias organization_alias_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_alias
    ADD CONSTRAINT organization_alias_pkey PRIMARY KEY (id);


--
-- Name: organization organization_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization
    ADD CONSTRAINT organization_pkey PRIMARY KEY (id);


--
-- Name: organization_relationship organization_relationship_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_relationship
    ADD CONSTRAINT organization_relationship_pkey PRIMARY KEY (id);


--
-- Name: organization_relationship organization_relationship_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_relationship
    ADD CONSTRAINT organization_relationship_uniq UNIQUE (from_organization_id, to_organization_id, relationship_type);


--
-- Name: organization organization_slug_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization
    ADD CONSTRAINT organization_slug_key UNIQUE (slug);


--
-- Name: person_role person_role_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.person_role
    ADD CONSTRAINT person_role_pkey PRIMARY KEY (id);


--
-- Name: person_suppression person_suppression_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.person_suppression
    ADD CONSTRAINT person_suppression_pkey PRIMARY KEY (id);


--
-- Name: provider_club provider_club_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.provider_club
    ADD CONSTRAINT provider_club_pkey PRIMARY KEY (id);


--
-- Name: provider_club provider_club_source_external_key_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.provider_club
    ADD CONSTRAINT provider_club_source_external_key_uniq UNIQUE (source, external_key);


--
-- Name: regatta_entry regatta_entry_event_external_key_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_entry
    ADD CONSTRAINT regatta_entry_event_external_key_uniq UNIQUE (event_id, external_key);


--
-- Name: regatta_entry regatta_entry_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_entry
    ADD CONSTRAINT regatta_entry_pkey PRIMARY KEY (id);


--
-- Name: regatta_event regatta_event_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_event
    ADD CONSTRAINT regatta_event_pkey PRIMARY KEY (id);


--
-- Name: regatta_event regatta_event_regatta_external_key_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_event
    ADD CONSTRAINT regatta_event_regatta_external_key_uniq UNIQUE (regatta_id, external_key);


--
-- Name: regatta regatta_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta
    ADD CONSTRAINT regatta_pkey PRIMARY KEY (id);


--
-- Name: regatta_result regatta_result_entry_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_result
    ADD CONSTRAINT regatta_result_entry_uniq UNIQUE (entry_id);


--
-- Name: regatta_result regatta_result_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_result
    ADD CONSTRAINT regatta_result_pkey PRIMARY KEY (id);


--
-- Name: regatta regatta_source_external_revision_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta
    ADD CONSTRAINT regatta_source_external_revision_uniq UNIQUE (source, external_key, revision);


--
-- Name: regatta_source_link regatta_source_link_event_date_outbound_url_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_source_link
    ADD CONSTRAINT regatta_source_link_event_date_outbound_url_uniq UNIQUE NULLS NOT DISTINCT (event_date, outbound_url);


--
-- Name: regatta_source_link regatta_source_link_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_source_link
    ADD CONSTRAINT regatta_source_link_pkey PRIMARY KEY (id);


--
-- Name: result_person result_person_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.result_person
    ADD CONSTRAINT result_person_pkey PRIMARY KEY (id);


--
-- Name: review_task review_task_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.review_task
    ADD CONSTRAINT review_task_pkey PRIMARY KEY (id);


--
-- Name: source_record source_record_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.source_record
    ADD CONSTRAINT source_record_pkey PRIMARY KEY (id);


--
-- Name: source_record source_record_source_external_checksum_uniq; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.source_record
    ADD CONSTRAINT source_record_source_external_checksum_uniq UNIQUE (source, external_key, checksum_sha256);


--
-- Name: ingest_run ingest_run_pkey; Type: CONSTRAINT; Schema: ops; Owner: -
--

ALTER TABLE ONLY ops.ingest_run
    ADD CONSTRAINT ingest_run_pkey PRIMARY KEY (id);


--
-- Name: publish_snapshot publish_snapshot_pkey; Type: CONSTRAINT; Schema: ops; Owner: -
--

ALTER TABLE ONLY ops.publish_snapshot
    ADD CONSTRAINT publish_snapshot_pkey PRIMARY KEY (id);


--
-- Name: quarantine quarantine_pkey; Type: CONSTRAINT; Schema: ops; Owner: -
--

ALTER TABLE ONLY ops.quarantine
    ADD CONSTRAINT quarantine_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: metric_catalog metric_catalog_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.metric_catalog
    ADD CONSTRAINT metric_catalog_pkey PRIMARY KEY (snapshot_id, metric_key, metric_version);


--
-- Name: org_directory org_directory_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_directory
    ADD CONSTRAINT org_directory_pkey PRIMARY KEY (snapshot_id, organization_id);


--
-- Name: org_directory org_directory_snapshot_slug_uniq; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_directory
    ADD CONSTRAINT org_directory_snapshot_slug_uniq UNIQUE (snapshot_id, slug);


--
-- Name: org_filing_coverage org_filing_coverage_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_filing_coverage
    ADD CONSTRAINT org_filing_coverage_pkey PRIMARY KEY (snapshot_id, organization_id, tax_year);


--
-- Name: org_financial_series org_financial_series_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_financial_series
    ADD CONSTRAINT org_financial_series_pkey PRIMARY KEY (id);


--
-- Name: org_financial_series org_financial_series_snapshot_series_uniq; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_financial_series
    ADD CONSTRAINT org_financial_series_snapshot_series_uniq UNIQUE (snapshot_id, organization_id, series_key, series_version, tax_year);


--
-- Name: org_peer_cohort org_peer_cohort_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_peer_cohort
    ADD CONSTRAINT org_peer_cohort_pkey PRIMARY KEY (snapshot_id, organization_id, cohort_key);


--
-- Name: org_profile org_profile_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_profile
    ADD CONSTRAINT org_profile_pkey PRIMARY KEY (snapshot_id, organization_id);


--
-- Name: org_slug_history org_slug_history_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_slug_history
    ADD CONSTRAINT org_slug_history_pkey PRIMARY KEY (slug);


--
-- Name: published_snapshot published_snapshot_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.published_snapshot
    ADD CONSTRAINT published_snapshot_pkey PRIMARY KEY (singleton);


--
-- Name: source_registry_public source_registry_public_pkey; Type: CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.source_registry_public
    ADD CONSTRAINT source_registry_public_pkey PRIMARY KEY (snapshot_id, source_key);


--
-- Name: bmf_row bmf_row_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.bmf_row
    ADD CONSTRAINT bmf_row_pkey PRIMARY KEY (id);


--
-- Name: efile_index_row efile_index_row_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.efile_index_row
    ADD CONSTRAINT efile_index_row_pkey PRIMARY KEY (id);


--
-- Name: epostcard_row epostcard_row_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.epostcard_row
    ADD CONSTRAINT epostcard_row_pkey PRIMARY KEY (id);


--
-- Name: filing_extract filing_extract_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.filing_extract
    ADD CONSTRAINT filing_extract_pkey PRIMARY KEY (id);


--
-- Name: herenow_catalog_row herenow_catalog_row_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_catalog_row
    ADD CONSTRAINT herenow_catalog_row_pkey PRIMARY KEY (id);


--
-- Name: herenow_catalog_row herenow_catalog_row_race_id_uniq; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_catalog_row
    ADD CONSTRAINT herenow_catalog_row_race_id_uniq UNIQUE (race_id);


--
-- Name: herenow_race_payload herenow_race_payload_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_race_payload
    ADD CONSTRAINT herenow_race_payload_pkey PRIMARY KEY (id);


--
-- Name: herenow_race_payload herenow_race_payload_race_kind_uniq; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_race_payload
    ADD CONSTRAINT herenow_race_payload_race_kind_uniq UNIQUE (race_id, kind);


--
-- Name: propublica_org propublica_org_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.propublica_org
    ADD CONSTRAINT propublica_org_pkey PRIMARY KEY (id);


--
-- Name: regattatiming_page regattatiming_page_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.regattatiming_page
    ADD CONSTRAINT regattatiming_page_pkey PRIMARY KEY (id);


--
-- Name: regattatiming_page regattatiming_page_race_id_key; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.regattatiming_page
    ADD CONSTRAINT regattatiming_page_race_id_key UNIQUE (race_id);


--
-- Name: row2k_index_page row2k_index_page_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.row2k_index_page
    ADD CONSTRAINT row2k_index_page_pkey PRIMARY KEY (id);


--
-- Name: time_team_race time_team_race_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_race
    ADD CONSTRAINT time_team_race_pkey PRIMARY KEY (id);


--
-- Name: time_team_race time_team_race_race_uuid_uniq; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_race
    ADD CONSTRAINT time_team_race_race_uuid_uniq UNIQUE (race_uuid);


--
-- Name: time_team_regatta time_team_regatta_pkey; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_regatta
    ADD CONSTRAINT time_team_regatta_pkey PRIMARY KEY (id);


--
-- Name: time_team_regatta time_team_regatta_slug_year_uniq; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_regatta
    ADD CONSTRAINT time_team_regatta_slug_year_uniq UNIQUE (slug, year);


--
-- Name: correction_submission_organization_id_idx; Type: INDEX; Schema: app; Owner: -
--

CREATE INDEX correction_submission_organization_id_idx ON app.correction_submission USING btree (organization_id);


--
-- Name: correction_submission_status_idx; Type: INDEX; Schema: app; Owner: -
--

CREATE INDEX correction_submission_status_idx ON app.correction_submission USING btree (status);


--
-- Name: audit_event_entity_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX audit_event_entity_idx ON core.audit_event USING btree (entity_type, entity_id);


--
-- Name: audit_event_occurred_at_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX audit_event_occurred_at_idx ON core.audit_event USING btree (occurred_at);


--
-- Name: audit_event_reversal_of_event_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX audit_event_reversal_of_event_id_idx ON core.audit_event USING btree (reversal_of_event_id);


--
-- Name: ein_observation_source_record_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ein_observation_source_record_id_idx ON core.ein_observation USING btree (source_record_id);


--
-- Name: epostcard_observation_ein_tax_year_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX epostcard_observation_ein_tax_year_idx ON core.epostcard_observation USING btree (ein, tax_year);


--
-- Name: epostcard_observation_source_record_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX epostcard_observation_source_record_id_idx ON core.epostcard_observation USING btree (source_record_id);


--
-- Name: external_identifier_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX external_identifier_organization_id_idx ON core.external_identifier USING btree (organization_id);


--
-- Name: external_identifier_verified_active_uniq; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX external_identifier_verified_active_uniq ON core.external_identifier USING btree (namespace, value) WHERE ((valid_to IS NULL) AND (verification_state = 'verified'::text));


--
-- Name: filing_ein_tax_period_end_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX filing_ein_tax_period_end_idx ON core.filing USING btree (ein, tax_period_end);


--
-- Name: filing_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX filing_organization_id_idx ON core.filing USING btree (organization_id);


--
-- Name: filing_source_record_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX filing_source_record_id_idx ON core.filing USING btree (source_record_id);


--
-- Name: filing_superseded_by_filing_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX filing_superseded_by_filing_id_idx ON core.filing USING btree (superseded_by_filing_id);


--
-- Name: filing_tax_year_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX filing_tax_year_idx ON core.filing USING btree (tax_year);


--
-- Name: financial_fact_concept_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX financial_fact_concept_idx ON core.financial_fact USING btree (concept);


--
-- Name: financial_fact_filing_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX financial_fact_filing_id_idx ON core.financial_fact USING btree (filing_id);


--
-- Name: metric_value_metric_definition_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX metric_value_metric_definition_idx ON core.metric_value USING btree (metric_key, metric_version);


--
-- Name: metric_value_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX metric_value_organization_id_idx ON core.metric_value USING btree (organization_id);


--
-- Name: metric_value_tax_year_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX metric_value_tax_year_idx ON core.metric_value USING btree (tax_year);


--
-- Name: organization_alias_normalized_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX organization_alias_normalized_idx ON core.organization_alias USING btree (alias_normalized);


--
-- Name: organization_alias_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX organization_alias_organization_id_idx ON core.organization_alias USING btree (organization_id);


--
-- Name: organization_merged_into_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX organization_merged_into_id_idx ON core.organization USING btree (merged_into_id);


--
-- Name: organization_relationship_from_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX organization_relationship_from_organization_id_idx ON core.organization_relationship USING btree (from_organization_id);


--
-- Name: organization_relationship_to_organization_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX organization_relationship_to_organization_id_idx ON core.organization_relationship USING btree (to_organization_id);


--
-- Name: person_role_filing_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX person_role_filing_id_idx ON core.person_role USING btree (filing_id);


--
-- Name: person_suppression_name_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX person_suppression_name_idx ON core.person_suppression USING btree (person_name_normalized);


--
-- Name: provider_club_display_name_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX provider_club_display_name_idx ON core.provider_club USING btree (lower(display_name));


--
-- Name: regatta_entry_event_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX regatta_entry_event_id_idx ON core.regatta_entry USING btree (event_id);


--
-- Name: regatta_entry_provider_club_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX regatta_entry_provider_club_id_idx ON core.regatta_entry USING btree (provider_club_id);


--
-- Name: regatta_event_regatta_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX regatta_event_regatta_id_idx ON core.regatta_event USING btree (regatta_id);


--
-- Name: regatta_source_external_key_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX regatta_source_external_key_idx ON core.regatta USING btree (source, external_key);


--
-- Name: regatta_start_date_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX regatta_start_date_idx ON core.regatta USING btree (start_date);


--
-- Name: result_person_entry_id_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX result_person_entry_id_idx ON core.result_person USING btree (entry_id);


--
-- Name: review_task_entity_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX review_task_entity_idx ON core.review_task USING btree (entity_type, entity_id);


--
-- Name: review_task_status_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX review_task_status_idx ON core.review_task USING btree (status);


--
-- Name: ingest_run_job_name_created_at_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX ingest_run_job_name_created_at_idx ON ops.ingest_run USING btree (job_name, created_at DESC);


--
-- Name: ingest_run_source_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX ingest_run_source_idx ON ops.ingest_run USING btree (source, started_at DESC);


--
-- Name: ingest_run_status_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX ingest_run_status_idx ON ops.ingest_run USING btree (status);


--
-- Name: publish_snapshot_ingest_run_id_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX publish_snapshot_ingest_run_id_idx ON ops.publish_snapshot USING btree (ingest_run_id);


--
-- Name: publish_snapshot_status_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX publish_snapshot_status_idx ON ops.publish_snapshot USING btree (status);


--
-- Name: quarantine_ingest_run_id_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX quarantine_ingest_run_id_idx ON ops.quarantine USING btree (ingest_run_id);


--
-- Name: quarantine_unresolved_idx; Type: INDEX; Schema: ops; Owner: -
--

CREATE INDEX quarantine_unresolved_idx ON ops.quarantine USING btree (created_at) WHERE (NOT resolved);


--
-- Name: org_directory_organization_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_directory_organization_id_idx ON read.org_directory USING btree (organization_id);


--
-- Name: org_directory_search_text_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_directory_search_text_idx ON read.org_directory USING gin (search_text);


--
-- Name: org_filing_coverage_organization_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_filing_coverage_organization_id_idx ON read.org_filing_coverage USING btree (organization_id);


--
-- Name: org_filing_coverage_tax_year_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_filing_coverage_tax_year_idx ON read.org_filing_coverage USING btree (tax_year);


--
-- Name: org_financial_series_organization_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_financial_series_organization_id_idx ON read.org_financial_series USING btree (organization_id);


--
-- Name: org_financial_series_snapshot_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_financial_series_snapshot_id_idx ON read.org_financial_series USING btree (snapshot_id);


--
-- Name: org_financial_series_tax_year_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_financial_series_tax_year_idx ON read.org_financial_series USING btree (tax_year);


--
-- Name: org_peer_cohort_cohort_key_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_peer_cohort_cohort_key_idx ON read.org_peer_cohort USING btree (cohort_key);


--
-- Name: org_peer_cohort_organization_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_peer_cohort_organization_id_idx ON read.org_peer_cohort USING btree (organization_id);


--
-- Name: org_profile_organization_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_profile_organization_id_idx ON read.org_profile USING btree (organization_id);


--
-- Name: org_slug_history_current_org_uniq; Type: INDEX; Schema: read; Owner: -
--

CREATE UNIQUE INDEX org_slug_history_current_org_uniq ON read.org_slug_history USING btree (org_id) WHERE is_current;


--
-- Name: org_slug_history_org_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_slug_history_org_id_idx ON read.org_slug_history USING btree (org_id);


--
-- Name: org_slug_history_snapshot_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX org_slug_history_snapshot_id_idx ON read.org_slug_history USING btree (snapshot_id);


--
-- Name: published_snapshot_snapshot_id_idx; Type: INDEX; Schema: read; Owner: -
--

CREATE INDEX published_snapshot_snapshot_id_idx ON read.published_snapshot USING btree (snapshot_id);


--
-- Name: bmf_row_ein_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX bmf_row_ein_idx ON staging.bmf_row USING btree (ein);


--
-- Name: bmf_row_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX bmf_row_ingest_run_id_idx ON staging.bmf_row USING btree (ingest_run_id);


--
-- Name: bmf_row_source_record_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX bmf_row_source_record_id_idx ON staging.bmf_row USING btree (source_record_id);


--
-- Name: efile_index_row_ein_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX efile_index_row_ein_idx ON staging.efile_index_row USING btree (ein);


--
-- Name: efile_index_row_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX efile_index_row_ingest_run_id_idx ON staging.efile_index_row USING btree (ingest_run_id);


--
-- Name: efile_index_row_object_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX efile_index_row_object_id_idx ON staging.efile_index_row USING btree (irs_object_id);


--
-- Name: efile_index_row_object_uq; Type: INDEX; Schema: staging; Owner: -
--

CREATE UNIQUE INDEX efile_index_row_object_uq ON staging.efile_index_row USING btree (irs_object_id);


--
-- Name: efile_index_row_source_record_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX efile_index_row_source_record_id_idx ON staging.efile_index_row USING btree (source_record_id);


--
-- Name: epostcard_row_ein_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX epostcard_row_ein_idx ON staging.epostcard_row USING btree (ein);


--
-- Name: epostcard_row_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX epostcard_row_ingest_run_id_idx ON staging.epostcard_row USING btree (ingest_run_id);


--
-- Name: epostcard_row_source_record_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX epostcard_row_source_record_id_idx ON staging.epostcard_row USING btree (source_record_id);


--
-- Name: filing_extract_ein_object_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX filing_extract_ein_object_id_idx ON staging.filing_extract USING btree (ein, irs_object_id);


--
-- Name: filing_extract_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX filing_extract_ingest_run_id_idx ON staging.filing_extract USING btree (ingest_run_id);


--
-- Name: filing_extract_object_uq; Type: INDEX; Schema: staging; Owner: -
--

CREATE UNIQUE INDEX filing_extract_object_uq ON staging.filing_extract USING btree (irs_object_id);


--
-- Name: filing_extract_source_record_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX filing_extract_source_record_id_idx ON staging.filing_extract USING btree (source_record_id);


--
-- Name: herenow_catalog_row_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX herenow_catalog_row_ingest_run_id_idx ON staging.herenow_catalog_row USING btree (ingest_run_id);


--
-- Name: herenow_race_payload_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX herenow_race_payload_ingest_run_id_idx ON staging.herenow_race_payload USING btree (ingest_run_id);


--
-- Name: propublica_org_ein_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX propublica_org_ein_idx ON staging.propublica_org USING btree (ein);


--
-- Name: propublica_org_ein_uq; Type: INDEX; Schema: staging; Owner: -
--

CREATE UNIQUE INDEX propublica_org_ein_uq ON staging.propublica_org USING btree (ein);


--
-- Name: propublica_org_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX propublica_org_ingest_run_id_idx ON staging.propublica_org USING btree (ingest_run_id);


--
-- Name: propublica_org_source_record_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX propublica_org_source_record_id_idx ON staging.propublica_org USING btree (source_record_id);


--
-- Name: regattatiming_page_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX regattatiming_page_ingest_run_id_idx ON staging.regattatiming_page USING btree (ingest_run_id);


--
-- Name: row2k_index_page_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX row2k_index_page_ingest_run_id_idx ON staging.row2k_index_page USING btree (ingest_run_id);


--
-- Name: time_team_race_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX time_team_race_ingest_run_id_idx ON staging.time_team_race USING btree (ingest_run_id);


--
-- Name: time_team_race_slug_year_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX time_team_race_slug_year_idx ON staging.time_team_race USING btree (slug, year);


--
-- Name: time_team_regatta_ingest_run_id_idx; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX time_team_regatta_ingest_run_id_idx ON staging.time_team_regatta USING btree (ingest_run_id);


--
-- Name: correction_submission correction_submission_organization_fk; Type: FK CONSTRAINT; Schema: app; Owner: -
--

ALTER TABLE ONLY app.correction_submission
    ADD CONSTRAINT correction_submission_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: audit_event audit_event_reversal_of_event_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.audit_event
    ADD CONSTRAINT audit_event_reversal_of_event_fk FOREIGN KEY (reversal_of_event_id) REFERENCES core.audit_event(id);


--
-- Name: ein_observation ein_observation_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.ein_observation
    ADD CONSTRAINT ein_observation_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: epostcard_observation epostcard_observation_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.epostcard_observation
    ADD CONSTRAINT epostcard_observation_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: external_identifier external_identifier_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.external_identifier
    ADD CONSTRAINT external_identifier_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: filing filing_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.filing
    ADD CONSTRAINT filing_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: filing filing_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.filing
    ADD CONSTRAINT filing_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: filing filing_superseded_by_filing_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.filing
    ADD CONSTRAINT filing_superseded_by_filing_fk FOREIGN KEY (superseded_by_filing_id) REFERENCES core.filing(id);


--
-- Name: financial_fact financial_fact_concept_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.financial_fact
    ADD CONSTRAINT financial_fact_concept_fk FOREIGN KEY (concept) REFERENCES core.concept_definition(concept);


--
-- Name: financial_fact financial_fact_filing_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.financial_fact
    ADD CONSTRAINT financial_fact_filing_fk FOREIGN KEY (filing_id) REFERENCES core.filing(id);


--
-- Name: metric_value metric_value_metric_definition_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.metric_value
    ADD CONSTRAINT metric_value_metric_definition_fk FOREIGN KEY (metric_key, metric_version) REFERENCES core.metric_definition(metric_key, version);


--
-- Name: metric_value metric_value_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.metric_value
    ADD CONSTRAINT metric_value_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: organization_alias organization_alias_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_alias
    ADD CONSTRAINT organization_alias_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: organization organization_merged_into_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization
    ADD CONSTRAINT organization_merged_into_fk FOREIGN KEY (merged_into_id) REFERENCES core.organization(id);


--
-- Name: organization_relationship organization_relationship_from_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_relationship
    ADD CONSTRAINT organization_relationship_from_organization_fk FOREIGN KEY (from_organization_id) REFERENCES core.organization(id);


--
-- Name: organization_relationship organization_relationship_to_organization_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.organization_relationship
    ADD CONSTRAINT organization_relationship_to_organization_fk FOREIGN KEY (to_organization_id) REFERENCES core.organization(id);


--
-- Name: person_role person_role_filing_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.person_role
    ADD CONSTRAINT person_role_filing_fk FOREIGN KEY (filing_id) REFERENCES core.filing(id);


--
-- Name: person_suppression person_suppression_provider_club_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.person_suppression
    ADD CONSTRAINT person_suppression_provider_club_fk FOREIGN KEY (provider_club_id) REFERENCES core.provider_club(id);


--
-- Name: provider_club provider_club_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.provider_club
    ADD CONSTRAINT provider_club_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: regatta_entry regatta_entry_event_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_entry
    ADD CONSTRAINT regatta_entry_event_fk FOREIGN KEY (event_id) REFERENCES core.regatta_event(id);


--
-- Name: regatta_entry regatta_entry_provider_club_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_entry
    ADD CONSTRAINT regatta_entry_provider_club_fk FOREIGN KEY (provider_club_id) REFERENCES core.provider_club(id);


--
-- Name: regatta_event regatta_event_regatta_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_event
    ADD CONSTRAINT regatta_event_regatta_fk FOREIGN KEY (regatta_id) REFERENCES core.regatta(id);


--
-- Name: regatta_result regatta_result_entry_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_result
    ADD CONSTRAINT regatta_result_entry_fk FOREIGN KEY (entry_id) REFERENCES core.regatta_entry(id);


--
-- Name: regatta_source_link regatta_source_link_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta_source_link
    ADD CONSTRAINT regatta_source_link_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: regatta regatta_source_record_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.regatta
    ADD CONSTRAINT regatta_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: result_person result_person_entry_fk; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.result_person
    ADD CONSTRAINT result_person_entry_fk FOREIGN KEY (entry_id) REFERENCES core.regatta_entry(id);


--
-- Name: publish_snapshot publish_snapshot_ingest_run_fk; Type: FK CONSTRAINT; Schema: ops; Owner: -
--

ALTER TABLE ONLY ops.publish_snapshot
    ADD CONSTRAINT publish_snapshot_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: quarantine quarantine_ingest_run_fk; Type: FK CONSTRAINT; Schema: ops; Owner: -
--

ALTER TABLE ONLY ops.quarantine
    ADD CONSTRAINT quarantine_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: metric_catalog metric_catalog_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.metric_catalog
    ADD CONSTRAINT metric_catalog_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_directory org_directory_organization_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_directory
    ADD CONSTRAINT org_directory_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: org_directory org_directory_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_directory
    ADD CONSTRAINT org_directory_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_filing_coverage org_filing_coverage_organization_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_filing_coverage
    ADD CONSTRAINT org_filing_coverage_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: org_filing_coverage org_filing_coverage_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_filing_coverage
    ADD CONSTRAINT org_filing_coverage_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_financial_series org_financial_series_organization_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_financial_series
    ADD CONSTRAINT org_financial_series_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: org_financial_series org_financial_series_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_financial_series
    ADD CONSTRAINT org_financial_series_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_peer_cohort org_peer_cohort_organization_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_peer_cohort
    ADD CONSTRAINT org_peer_cohort_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: org_peer_cohort org_peer_cohort_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_peer_cohort
    ADD CONSTRAINT org_peer_cohort_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_profile org_profile_organization_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_profile
    ADD CONSTRAINT org_profile_organization_fk FOREIGN KEY (organization_id) REFERENCES core.organization(id);


--
-- Name: org_profile org_profile_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_profile
    ADD CONSTRAINT org_profile_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: org_slug_history org_slug_history_org_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_slug_history
    ADD CONSTRAINT org_slug_history_org_fk FOREIGN KEY (org_id) REFERENCES core.organization(id);


--
-- Name: org_slug_history org_slug_history_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.org_slug_history
    ADD CONSTRAINT org_slug_history_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: published_snapshot published_snapshot_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.published_snapshot
    ADD CONSTRAINT published_snapshot_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: source_registry_public source_registry_public_snapshot_fk; Type: FK CONSTRAINT; Schema: read; Owner: -
--

ALTER TABLE ONLY read.source_registry_public
    ADD CONSTRAINT source_registry_public_snapshot_fk FOREIGN KEY (snapshot_id) REFERENCES ops.publish_snapshot(id);


--
-- Name: bmf_row bmf_row_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.bmf_row
    ADD CONSTRAINT bmf_row_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: bmf_row bmf_row_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.bmf_row
    ADD CONSTRAINT bmf_row_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: efile_index_row efile_index_row_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.efile_index_row
    ADD CONSTRAINT efile_index_row_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: efile_index_row efile_index_row_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.efile_index_row
    ADD CONSTRAINT efile_index_row_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: epostcard_row epostcard_row_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.epostcard_row
    ADD CONSTRAINT epostcard_row_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: epostcard_row epostcard_row_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.epostcard_row
    ADD CONSTRAINT epostcard_row_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: filing_extract filing_extract_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.filing_extract
    ADD CONSTRAINT filing_extract_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: filing_extract filing_extract_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.filing_extract
    ADD CONSTRAINT filing_extract_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: herenow_catalog_row herenow_catalog_row_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_catalog_row
    ADD CONSTRAINT herenow_catalog_row_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: herenow_catalog_row herenow_catalog_row_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_catalog_row
    ADD CONSTRAINT herenow_catalog_row_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: herenow_race_payload herenow_race_payload_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_race_payload
    ADD CONSTRAINT herenow_race_payload_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: herenow_race_payload herenow_race_payload_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.herenow_race_payload
    ADD CONSTRAINT herenow_race_payload_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: propublica_org propublica_org_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.propublica_org
    ADD CONSTRAINT propublica_org_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: propublica_org propublica_org_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.propublica_org
    ADD CONSTRAINT propublica_org_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: regattatiming_page regattatiming_page_ingest_run_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.regattatiming_page
    ADD CONSTRAINT regattatiming_page_ingest_run_id_fkey FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: regattatiming_page regattatiming_page_source_record_id_fkey; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.regattatiming_page
    ADD CONSTRAINT regattatiming_page_source_record_id_fkey FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: row2k_index_page row2k_index_page_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.row2k_index_page
    ADD CONSTRAINT row2k_index_page_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: row2k_index_page row2k_index_page_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.row2k_index_page
    ADD CONSTRAINT row2k_index_page_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: time_team_race time_team_race_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_race
    ADD CONSTRAINT time_team_race_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: time_team_race time_team_race_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_race
    ADD CONSTRAINT time_team_race_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- Name: time_team_regatta time_team_regatta_ingest_run_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_regatta
    ADD CONSTRAINT time_team_regatta_ingest_run_fk FOREIGN KEY (ingest_run_id) REFERENCES ops.ingest_run(id);


--
-- Name: time_team_regatta time_team_regatta_source_record_fk; Type: FK CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.time_team_regatta
    ADD CONSTRAINT time_team_regatta_source_record_fk FOREIGN KEY (source_record_id) REFERENCES core.source_record(id);


--
-- PostgreSQL database dump complete
--

\unrestrict dbmate



--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('001'),
    ('002'),
    ('003'),
    ('004'),
    ('005'),
    ('006'),
    ('007'),
    ('008'),
    ('009'),
    ('010'),
    ('011'),
    ('012'),
    ('013'),
    ('014'),
    ('015'),
    ('016');
