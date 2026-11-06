"""Tools that inspect fixture files and save an archive manifest."""

from __future__ import annotations

import json
from pathlib import Path

from slimconfig import plain_output

from contract import (
    ArchiveManifestOutput,
    ReadArchiveRequestInput,
    ReadArchiveRequestOutput,
    WriteManifestInput,
    WriteManifestOutput,
)
from verifier.rules import collect_available_files, validate_manifest_entries


def read_archive_request(
    given: ReadArchiveRequestInput,
    workspace: Path,
) -> ReadArchiveRequestOutput:
    """Return the request and metadata for every available fixture file."""

    available_files = collect_available_files(given.task, workspace)
    return ReadArchiveRequestOutput(
        fixture_directory=given.task.fixture_directory,
        include_patterns=given.task.include_patterns,
        exclude_patterns=given.task.exclude_patterns,
        available_files=available_files,
    )


def write_manifest(
    given: WriteManifestInput,
    workspace: Path,
) -> WriteManifestOutput:
    """Write the agent's final structured manifest into its workspace."""

    collect_available_files(given.task, workspace)
    validate_manifest_entries(given.entries)

    report = ArchiveManifestOutput(entries=given.entries)
    report_path = Path(workspace) / "archive-manifest.json"
    report_path.write_text(
        json.dumps(plain_output(report), indent=2) + "\n",
        encoding="utf-8",
    )

    return WriteManifestOutput(
        report_path="archive-manifest.json",
        report=report,
    )
