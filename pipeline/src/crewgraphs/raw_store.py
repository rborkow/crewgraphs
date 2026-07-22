"""Immutable raw-object storage backed by Cloudflare R2's S3 API."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from .config import Settings
from .db import DatabaseGateway


class QuarantineableError(RuntimeError):
    """An input condition that callers should record in ``ops.quarantine``."""


class S3Client(Protocol):
    def head_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class RawObject:
    uri: str
    checksum_sha256: str
    size: int


class RawStore:
    """R2 wrapper enforcing one checksum per object key."""

    def __init__(self, settings: Settings, client: S3Client | None = None) -> None:
        self.bucket = settings.r2_bucket
        self._client = client or self._create_client(settings)

    @staticmethod
    def _create_client(settings: Settings) -> S3Client:
        # Lazy import keeps all fake-client tests entirely offline.
        import boto3

        return boto3.client(
            "s3",
            endpoint_url=(
                f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
            ),
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

    def put_raw(self, key: str, content_bytes: bytes, content_type: str) -> RawObject:
        checksum = hashlib.sha256(content_bytes).hexdigest()
        try:
            existing = self._client.head_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # S3-compatible clients use provider-specific errors.
            if not _is_not_found(exc):
                raise
        else:
            existing_checksum = _checksum_from_head(existing)
            size = int(existing.get("ContentLength", 0))
            if existing_checksum == checksum:
                return self._raw_object(key, checksum, size)
            raise QuarantineableError(
                f"raw object checksum conflict for {key}: "
                f"existing={existing_checksum or 'unknown'}, incoming={checksum}"
            )

        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content_bytes,
            ContentType=content_type,
            Metadata={"sha256": checksum},
        )
        return self._raw_object(key, checksum, len(content_bytes))

    def get_raw(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        return body.read() if hasattr(body, "read") else bytes(body)

    def _raw_object(self, key: str, checksum: str, size: int) -> RawObject:
        return RawObject(
            uri=f"r2://{self.bucket}/{key}", checksum_sha256=checksum, size=size
        )


def register_source_record(
    db: DatabaseGateway,
    *,
    source: str,
    external_key: str,
    raw_object: RawObject,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    """Create (or return) the immutable database pointer for a raw object.

    The table's real uniqueness boundary is ``(source, external_key,
    checksum_sha256)``.  Repeating the same immutable source pointer is safe;
    a changed raw payload produces a distinct source record.
    """
    params = (
        source,
        external_key,
        raw_object.checksum_sha256,
        raw_object.uri,
        json.dumps(dict(metadata or {})),
    )
    rows = db.execute(
        """
        INSERT INTO core.source_record
            (source, external_key, checksum_sha256, raw_uri, metadata)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (source, external_key, checksum_sha256) DO NOTHING
        RETURNING id
        """,
        params,
    )
    if rows:
        return str(rows[0]["id"])
    rows = db.execute(
        """
        SELECT id FROM core.source_record
        WHERE source = %s AND external_key = %s AND checksum_sha256 = %s
        """,
        params[:3],
    )
    if not rows:
        raise RuntimeError("source record disappeared after conflict")
    return str(rows[0]["id"])


def _checksum_from_head(response: dict[str, Any]) -> str | None:
    metadata = response.get("Metadata") or {}
    return metadata.get("sha256") or metadata.get("SHA256")


def _is_not_found(error: Exception) -> bool:
    """Recognize the 404 variants exposed by boto3 and small test fakes."""
    response = getattr(error, "response", None)
    code = (response or {}).get("Error", {}).get("Code")
    return code in {"404", "NoSuchKey", "NotFound"} or isinstance(error, KeyError)
