from typer.testing import CliRunner

from crewgraphs.__main__ import app


def test_help_lists_every_stub_subcommand() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
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
        "publish-gate",
        "rollback",
        "backfill",
        "curation",
        "run-report",
    ):
        assert command in result.output
