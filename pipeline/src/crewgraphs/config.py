"""Configuration for pipeline jobs, loaded explicitly from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when one or more required pipeline settings are absent."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Credentials and identifiers shared by pipeline jobs."""

    database_url: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str = "crewgraphs-raw"
    git_sha: str | None = None
    # Optional S3-endpoint override for local smokes/tests (e.g. MinIO);
    # unset means the real R2 endpoint derived from the account id.
    r2_endpoint_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        required = (
            "DATABASE_URL",
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
        )
        missing = [name for name in required if not values.get(name)]
        if missing:
            raise ConfigurationError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        return cls(
            database_url=values["DATABASE_URL"],
            r2_account_id=values["R2_ACCOUNT_ID"],
            r2_access_key_id=values["R2_ACCESS_KEY_ID"],
            r2_secret_access_key=values["R2_SECRET_ACCESS_KEY"],
            r2_bucket=values.get("R2_BUCKET") or "crewgraphs-raw",
            git_sha=values.get("GIT_SHA") or None,
            r2_endpoint_url=values.get("R2_ENDPOINT_URL") or None,
        )
