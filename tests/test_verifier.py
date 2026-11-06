import hashlib
from pathlib import Path

from contract import (
    ArchiveFile,
    ArchiveManifestInput,
    ArchiveManifestOutput,
    Task,
    Tool,
    WriteManifestInput,
    WriteManifestOutput,
)
from plugin.tools import write_manifest
from verifier import verify_input, verify_output
from verifier import verify_task as verify_registered_task
from verifier.rules import build_manifest
from verifier.task import verify_task


def prepare_task(workspace: Path) -> ArchiveManifestInput:
    fixture = workspace / "fixture"
    (fixture / "nested").mkdir(parents=True)
    (fixture / "a.txt").write_bytes(b"A\n")
    (fixture / "nested" / "b.txt").write_bytes(b"B\n")
    (fixture / "nested" / "skip.tmp").write_bytes(b"skip\n")
    return ArchiveManifestInput(
        fixture_directory="fixture",
        include_patterns=["**/*.txt"],
        exclude_patterns=["nested/b*"],
    )


def test_verifier_accepts_correct_manifest(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)
    output = ArchiveManifestOutput(entries=build_manifest(task, tmp_path))

    result = verify_task(task, output, reference=None, workspace=tmp_path)

    assert result.ok is True
    assert result.score == 1.0
    assert result.errors == []


def test_verifier_rejects_wrong_hash(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)
    expected = build_manifest(task, tmp_path)[0]
    output = ArchiveManifestOutput(
        entries=[ArchiveFile(expected.path, expected.size, "0" * 64)]
    )

    result = verify_task(task, output, reference=None, workspace=tmp_path)

    assert result.ok is False
    assert result.score == 0.0
    assert "does not match" in result.errors[0]
    assert expected.path in result.errors[0]


def test_verifier_rejects_missing_and_extra_entries(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)
    output = ArchiveManifestOutput(
        entries=[
            ArchiveFile(
                path="extra.txt",
                size=1,
                sha256=hashlib.sha256(b"x").hexdigest(),
            )
        ]
    )

    result = verify_task(task, output, reference=None, workspace=tmp_path)

    assert result.ok is False
    assert any("Missing manifest entry" in error for error in result.errors)
    assert any("Unexpected manifest entry" in error for error in result.errors)


def test_verifier_rejects_unsorted_entries(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)
    task.exclude_patterns = []
    expected = build_manifest(task, tmp_path)

    result = verify_task(
        task,
        ArchiveManifestOutput(entries=list(reversed(expected))),
        reference=None,
        workspace=tmp_path,
    )

    assert result.ok is False
    assert result.errors == ["entries must be sorted by path in ascending lexical order."]


def test_registered_verifier_dispatches_to_task_verifier(tmp_path: Path) -> None:
    task = prepare_task(tmp_path)

    result = verify_registered_task(
        Task.BUILD_ARCHIVE_MANIFEST.value,
        task,
        ArchiveManifestOutput(entries=build_manifest(task, tmp_path)),
        reference=None,
        workspace=tmp_path,
    )

    assert result["valid"] is True
    assert result["score"] == 1.0


def test_read_request_input_verifier_rejects_unsafe_task() -> None:
    task = ArchiveManifestInput(
        fixture_directory="../outside",
        include_patterns=[],
        exclude_patterns=[],
    )

    result = verify_input(
        Tool.READ_ARCHIVE_REQUEST.value,
        type("ReadRequestValue", (), {"task": task})(),
    )

    assert result["valid"] is False
    assert "normalized relative path" in result["details"]["errors"][0]


def test_write_manifest_output_verifier_requires_persisted_report(
    tmp_path: Path,
) -> None:
    task = prepare_task(tmp_path)
    entries = build_manifest(task, tmp_path)
    input_value = WriteManifestInput(task=task, entries=entries)
    output_value = WriteManifestOutput(
        report_path="archive-manifest.json",
        report=ArchiveManifestOutput(entries=entries),
    )

    result = verify_output(
        Tool.WRITE_MANIFEST.value,
        input_value,
        output_value,
        tmp_path,
    )

    assert result["valid"] is False
    assert result["details"]["errors"] == ["archive-manifest.json is missing."]


def test_write_manifest_output_verifier_accepts_persisted_report(
    tmp_path: Path,
) -> None:
    task = prepare_task(tmp_path)
    entries = build_manifest(task, tmp_path)
    input_value = WriteManifestInput(task=task, entries=entries)
    output_value = write_manifest(input_value, tmp_path)

    result = verify_output(
        Tool.WRITE_MANIFEST.value,
        input_value,
        output_value,
        str(tmp_path),
    )

    assert result["valid"] is True
