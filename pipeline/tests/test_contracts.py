"""Validate that Python-side payloads satisfy the exported contract schemas.

The zod schemas in packages/contracts are the cross-tier source of truth;
they are exported as JSON Schema (draft 2020-12) so this side can prove the
jsonb payloads it publishes are readable by the web tier. Fixture payloads
(db/fixtures/payloads/*.json) are validated too when present.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "packages" / "contracts" / "schemas"
FIXTURE_PAYLOAD_DIR = REPO_ROOT / "db" / "fixtures" / "payloads"


def load_schema(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMA_DIR / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


SAMPLE_SOURCE_REF = {
    "value": 125000,
    "unit": "USD",
    "period": {"tax_year": 2024, "fy_end": "2025-06-30", "label": "FY2024 (Jul 2024–Jun 2025)"},
    "quality_state": "verified",
    "source": {
        "source_key": "irs_990_xml",
        "form_type": "990",
        "filing_id": "3f4c8a1e-0000-4000-8000-000000000001",
        "source_path": "/Return/ReturnData/IRS990/CYTotalRevenueAmt",
        "raw_url": "https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/202121129349301317_public.xml",
        "is_amended": False,
    },
    "retrieved_at": "2026-07-21T12:00:00Z",
    "parser_version": "cm-2026.07.1",
    "metric": None,
}


def test_source_ref_schema_accepts_valid_payload() -> None:
    validator = load_schema("source-ref.v1.schema.json")
    validator.validate(SAMPLE_SOURCE_REF)


def test_source_ref_schema_rejects_missing_provenance() -> None:
    validator = load_schema("source-ref.v1.schema.json")
    broken = {**SAMPLE_SOURCE_REF, "source": None}
    assert list(validator.iter_errors(broken)), "provenance-less ref must not validate"


def test_source_ref_schema_rejects_missing_tax_year() -> None:
    validator = load_schema("source-ref.v1.schema.json")
    period = {k: v for k, v in SAMPLE_SOURCE_REF["period"].items() if k != "tax_year"}
    assert list(validator.iter_errors({**SAMPLE_SOURCE_REF, "period": period}))


@pytest.mark.skipif(not FIXTURE_PAYLOAD_DIR.exists(), reason="fixture payloads not present yet")
def test_fixture_payloads_validate() -> None:
    validator = load_schema("org-profile-payload.v1.schema.json")
    payloads = sorted(FIXTURE_PAYLOAD_DIR.glob("*.json"))
    assert payloads, "payload dir exists but is empty"
    for path in payloads:
        errors = list(validator.iter_errors(json.loads(path.read_text())))
        assert not errors, f"{path.name}: {[e.message for e in errors][:3]}"
