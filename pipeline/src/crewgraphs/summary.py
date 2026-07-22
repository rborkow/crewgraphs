"""GitHub Actions-compatible Markdown summaries for pipeline runs."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO


def render_summary(
    *,
    job_name: str,
    run_id: str,
    status: str,
    counts: Mapping[str, int] | None = None,
    warnings: Sequence[str] | None = None,
    quarantines: int = 0,
) -> str:
    """Render an intentionally small Markdown run report."""
    lines = [
        f"## CrewGraphs pipeline: `{job_name}`",
        "",
        f"- Run: `{run_id}`",
        f"- Status: **{status}**",
        f"- Quarantines: **{quarantines}**",
    ]
    if counts:
        lines.extend(["", "### Counts", ""])
        lines.extend(f"- {key}: **{value}**" for key, value in counts.items())
    if warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def emit_summary(markdown: str, *, env: Mapping[str, str] | None = None, stdout: TextIO | None = None) -> None:
    """Append to GitHub's summary file, or write to stdout outside Actions."""
    values = os.environ if env is None else env
    summary_path = values.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(markdown)
        return
    (stdout or sys.stdout).write(markdown)
