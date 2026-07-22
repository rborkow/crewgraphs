"""Small shared pieces for CrewGraphs acquisition jobs."""

from __future__ import annotations

import re

from ..db import DatabaseGateway


# This is intentionally a discovery sweep, rather than an identity decision.  In
# particular, the CREW alternative is deliberately broad enough to catch names
# such as "Crewe"; review/resolution decides whether a discovery is in scope.
DISCOVERY_NAME_RE = re.compile(
    r"(?<![A-Z0-9])(?:ROWING|CREW|BOAT[ -]?CLUB|SCULL|REGATTA|OARS)", re.IGNORECASE
)


def verified_irs_eins(db: DatabaseGateway) -> set[str]:
    """Return the current verified IRS-EIN watchlist from the identity layer."""
    rows = db.execute(
        """
        SELECT value AS ein
        FROM core.external_identifier
        WHERE namespace = 'irs_ein'
          AND verification_state = 'verified'
        """
    )
    return {str(row["ein"]) for row in rows if row.get("ein")}


def normalized_ein(value: object) -> str | None:
    """Normalize an IRS EIN to the schema's nine-digit representation."""
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits if len(digits) == 9 else None


def is_discovery_name(name: object) -> bool:
    """Whether a legal name belongs in the intentionally broad discovery sweep."""
    return bool(DISCOVERY_NAME_RE.search(str(name or "")))
