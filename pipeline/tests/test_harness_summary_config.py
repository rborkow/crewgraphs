from __future__ import annotations

from crewgraphs.config import ConfigurationError, Settings
from crewgraphs.summary import emit_summary, render_summary


def test_summary_includes_counts_and_writes_github_summary(tmp_path) -> None:
    destination = tmp_path / "summary.md"
    markdown = render_summary(
        job_name="run_report",
        run_id="run-1",
        status="succeeded",
        counts={"source_records": 4},
        warnings=["late file"],
        quarantines=2,
    )

    emit_summary(markdown, env={"GITHUB_STEP_SUMMARY": str(destination)})

    text = destination.read_text()
    assert "source_records: **4**" in text
    assert "Quarantines: **2**" in text
    assert "late file" in text


def test_config_reports_every_missing_variable() -> None:
    try:
        Settings.from_env({})
    except ConfigurationError as error:
        message = str(error)
    else:
        raise AssertionError("expected ConfigurationError")

    for name in (
        "DATABASE_URL",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    ):
        assert name in message
