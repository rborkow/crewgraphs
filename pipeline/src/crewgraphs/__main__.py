from __future__ import annotations

import contextlib
from datetime import date
from typing import Any, Iterator

import typer

from .config import Settings
from .db import DatabaseGateway, PostgresGateway
from .raw_store import RawStore
from .runlog import IngestRun
from .summary import emit_summary, render_summary

app = typer.Typer(help="CrewGraphs ingestion pipeline.")

USER_AGENT = "CrewGraphs/0.1 (public IRS data pipeline; crewgraphs.com/methods)"


@contextlib.contextmanager
def _job_context() -> Iterator[tuple[DatabaseGateway, RawStore, Any]]:
    import httpx

    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    store = RawStore(settings)
    http = httpx.Client(
        timeout=httpx.Timeout(300.0, connect=30.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    try:
        yield gateway, store, http
    finally:
        http.close()
        gateway.close()


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def not_implemented() -> None:
    typer.echo("not implemented")
    raise typer.Exit(code=1)


for command_name in (
    "backfill",
    "curation",
):
    app.command(name=command_name)(not_implemented)


@app.command(name="seed-load")
def seed_load_cmd(
    csv_path: str = typer.Option("seed/cohort.csv", help="Path to the curated cohort CSV"),
    actor: str = typer.Option("owner", help="Audit-event actor"),
) -> None:
    """Load the curated cohort as the curator role (audited identity writes)."""
    import os

    from .jobs.seed_load import seed_load

    curator_url = os.environ.get("CURATOR_DATABASE_URL")
    if not curator_url:
        typer.echo("CURATOR_DATABASE_URL is required (identity writes are curator-only)")
        raise typer.Exit(code=1)
    gateway = PostgresGateway(curator_url)
    try:
        typer.echo(seed_load(gateway, csv_path=csv_path, actor=actor))
    finally:
        gateway.close()


def _db_only_command(job) -> None:
    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    try:
        emit_summary(job(gateway))
    finally:
        gateway.close()


@app.command(name="resolve")
def resolve_cmd() -> None:
    """Sanity-check staged EINs against the identity graph; open review tasks."""
    from .jobs.resolve import resolve

    _db_only_command(resolve)


@app.command(name="derive")
def derive_cmd() -> None:
    """Derive canonical filings, facts, people, and metrics from staging."""
    from .jobs.derive import derive

    _db_only_command(derive)


@app.command(name="publish")
def publish_cmd(
    generated_at: str = typer.Option(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        help="ISO timestamp stamped into published payloads",
    ),
) -> None:
    """Build a read-model snapshot, validate contracts, atomically flip the pointer."""
    from .jobs.publish import publish

    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    try:
        emit_summary(publish(gateway, generated_at=generated_at))
    finally:
        gateway.close()


@app.command(name="publish-gate")
def publish_gate_cmd(
    since: str = typer.Option(..., help="ISO 8601 timestamp at which this pipeline chain started"),
) -> None:
    """Block publishing when this pipeline chain produced quarantines."""
    from .jobs.publish_gate import PublishGateFailure, publish_gate

    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    try:
        try:
            publish_gate(gateway, since=since)
        except PublishGateFailure as error:
            typer.echo(f"Publish gate blocked by {len(error.rows)} quarantine(s):")
            for row in error.rows:
                typer.echo(
                    "- "
                    f"job_name={row['job_name']} "
                    f"reason={row['reason']} "
                    f"external_key={row['external_key']}"
                )
            raise typer.Exit(code=1)
        typer.echo(f"Publish gate clear: no quarantines since {since}.")
    finally:
        gateway.close()


@app.command(name="rollback")
def rollback_cmd() -> None:
    """Repoint the published snapshot to the previous eligible snapshot."""
    from .jobs.rollback import rollback_publish

    _db_only_command(rollback_publish)


@app.command(name="bmf-sync")
def bmf_sync_cmd(
    states: str = typer.Option(..., help="Comma-separated state codes, e.g. pa,ma,nh"),
    eins: str = typer.Option("", help="Optional comma-separated EIN watchlist override"),
) -> None:
    """Sync IRS EO BMF state extracts into staging and ein_observation."""
    from .jobs.bmf import bmf_sync

    with _job_context() as (db, store, http):
        emit_summary(
            bmf_sync(
                db,
                store,
                http,
                states=[s.lower() for s in _csv(states)],
                watchlist_eins=set(_csv(eins)) or None,
            )
        )


@app.command(name="epostcard-sync")
def epostcard_sync_cmd(
    eins: str = typer.Option("", help="Optional comma-separated EIN watchlist override"),
) -> None:
    """Sync the IRS 990-N e-Postcard bulk file."""
    from .jobs.epostcard import epostcard_sync

    with _job_context() as (db, store, http):
        emit_summary(
            epostcard_sync(db, store, http, watchlist_eins=set(_csv(eins)) or None)
        )


@app.command(name="efile-index-sync")
def efile_index_sync_cmd(
    years: str = typer.Option(..., help="Comma-separated index years, e.g. 2020,2021,2024"),
    eins: str = typer.Option("", help="Optional comma-separated EIN watchlist override"),
) -> None:
    """Sync IRS e-file index CSVs for watchlist EINs (990/990-EZ only)."""
    from .jobs.efile_index import efile_index_sync

    with _job_context() as (db, store, http):
        result = efile_index_sync(
            db,
            store,
            http,
            years=[int(y) for y in _csv(years)],
            watchlist_eins=_csv(eins) or None,
        )
        emit_summary(str(result))


@app.command(name="efile-fetch")
def efile_fetch_cmd(
    object_ids: str = typer.Option("", help="Optional comma-separated object ids; default = staged, unfetched"),
) -> None:
    """Fetch staged filing XMLs from the GivingTuesday data lake into R2."""
    from .jobs.efile_fetch import efile_fetch

    with _job_context() as (db, store, http):
        result = efile_fetch(db, store, http, object_ids=_csv(object_ids) or None)
        emit_summary(str(result))


@app.command(name="efile-parse")
def efile_parse_cmd(
    object_ids: str = typer.Option("", help="Optional comma-separated object ids; default = fetched, unparsed"),
    reparse: bool = typer.Option(
        False,
        "--reparse",
        help="Re-extract already-parsed filings and overwrite their staging rows",
    ),
) -> None:
    """Extract the 24-concept map from fetched XMLs into staging.filing_extract."""
    from .jobs.efile_parse import efile_parse

    with _job_context() as (db, store, _http):
        result = efile_parse(db, store, object_ids=_csv(object_ids) or None, reparse=reparse)
        emit_summary(str(result))


@app.command(name="propublica-bootstrap")
def propublica_bootstrap_cmd(
    eins: str = typer.Option("", help="Optional comma-separated EINs; default = verified watchlist"),
    retrieved_date: str = typer.Option(default_factory=lambda: date.today().isoformat()),
) -> None:
    """Snapshot ProPublica organization payloads for discovery and cross-checks."""
    from .jobs.propublica import propublica_bootstrap

    with _job_context() as (db, store, http):
        emit_summary(
            propublica_bootstrap(
                db, store, http, eins=_csv(eins) or None, retrieved_date=retrieved_date
            )
        )


@app.command(name="cross-check")
def cross_check_cmd() -> None:
    """Compare parsed anchor concepts against ProPublica; mismatches open review tasks."""
    from .jobs.cross_check import cross_check

    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    try:
        emit_summary(cross_check(gateway))
    finally:
        gateway.close()


def run_report_job(db: DatabaseGateway, settings: Settings) -> str:
    """Run the minimal report job through the same lifecycle as future jobs."""
    with IngestRun(
        db,
        job_name="run_report",
        source="ops",
        git_sha=settings.git_sha,
        code_version="0.0.0",
    ) as run:
        counts = _run_report_counts(db, run.id or "")
        for key, value in counts.items():
            run.add_stat(key, value)
    return render_summary(
        job_name=run.job_name,
        run_id=run.id or "unknown",
        status="succeeded",
        counts=counts,
        warnings=run.stats.get("warnings", []),
        quarantines=counts["quarantines"],
    )


def _run_report_counts(db: DatabaseGateway, run_id: str) -> dict[str, int]:
    queries = {
        "ingest_runs": "SELECT count(*) AS count FROM ops.ingest_run",
        "source_records": "SELECT count(*) AS count FROM core.source_record",
        "quarantines": "SELECT count(*) AS count FROM ops.quarantine WHERE ingest_run_id = %s",
    }
    counts: dict[str, int] = {}
    for key, query in queries.items():
        params: tuple[str, ...] | None = (run_id,) if key == "quarantines" else None
        rows = db.execute(query, params)
        counts[key] = int(rows[0]["count"]) if rows else 0
    return counts


@app.command(name="run-report")
def run_report() -> None:
    """Emit an operations count summary through the pipeline run harness."""
    settings = Settings.from_env()
    gateway = PostgresGateway(settings.database_url)
    try:
        emit_summary(run_report_job(gateway, settings))
    finally:
        gateway.close()


if __name__ == "__main__":
    app()
