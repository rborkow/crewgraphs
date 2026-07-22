from __future__ import annotations

from typing import Any

import typer

from .config import Settings
from .db import DatabaseGateway, PostgresGateway
from .runlog import IngestRun
from .summary import emit_summary, render_summary

app = typer.Typer(help="CrewGraphs ingestion pipeline.")


def not_implemented() -> None:
    typer.echo("not implemented")
    raise typer.Exit(code=1)


for command_name in (
    "bmf-sync",
    "efile-index-sync",
    "efile-fetch",
    "efile-parse",
    "epostcard-sync",
    "propublica-bootstrap",
    "resolve",
    "derive",
    "cross-check",
    "publish",
    "rollback",
    "backfill",
    "curation",
):
    app.command(name=command_name)(not_implemented)


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
