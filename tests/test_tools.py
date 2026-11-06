import hashlib
import json
from pathlib import Path

from contract import (
    ArchiveFile,
    ArchiveManifestInput,
    ReadArchiveRequestInput,
    WriteManifestInput,
)
from plugin.tools import read_archive_request, write_manifest


def prepare_task(workspace: Path) -> ArchiveManifestInput:
    fixture = workspace / "fixture"
    fixture.mkdir()
    (fixture / "alpha.txt").write_bytes(b"alpha\n")
    (fixture / "ignored.tmp").write_bytes(b"ignore\n")
    return ArchiveManifestInput(
        fixture_directory="fixture",
        include_patterns=["**/*.txt"],
        exclude_patterns=[],
    )


def test_read_archive_request_returns_request_and_file_metadata(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)

    result = read_archive_request(ReadArchiveRequestInput(task=task), tmp_path)

    assert result.fixture_directory == "fixture"
    assert result.include_patterns == ["**/*.txt"]
    assert result.exclude_patterns == []
    assert [file.path for file in result.available_files] == [
        "alpha.txt",
        "ignored.tmp",
    ]
    assert result.available_files[0] == ArchiveFile(
        path="alpha.txt",
        size=6,
        sha256=hashlib.sha256(b"alpha\n").hexdigest(),
    )


def test_write_manifest_saves_structured_json_report(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)
    entry = ArchiveFile(
        path="alpha.txt",
        size=6,
        sha256=hashlib.sha256(b"alpha\n").hexdigest(),
    )

    result = write_manifest(
        WriteManifestInput(task=task, entries=[entry]),
        tmp_path,
    )

    assert result.report_path == "archive-manifest.json"
    assert result.report.entries == [entry]
    assert json.loads(
        (tmp_path / "archive-manifest.json").read_text(encoding="utf-8")
    ) == {
        "entries": [
            {
                "path": "alpha.txt",
                "size": 6,
                "sha256": hashlib.sha256(b"alpha\n").hexdigest(),
            }
        ]
    }


def test_existing_report_is_not_exposed_when_fixture_is_workspace(tmp_path: Path) -> None:
    (tmp_path / "payload.txt").write_text("payload\n", encoding="utf-8")
    (tmp_path / "archive-manifest.json").write_text("{}\n", encoding="utf-8")
    task = ArchiveManifestInput(
        fixture_directory=".",
        include_patterns=[],
        exclude_patterns=[],
    )

    result = read_archive_request(ReadArchiveRequestInput(task=task), tmp_path)

    assert [file.path for file in result.available_files] == ["payload.txt"]
