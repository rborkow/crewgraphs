import typer

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
    "run-report",
):
    app.command(name=command_name)(not_implemented)


if __name__ == "__main__":
    app()
