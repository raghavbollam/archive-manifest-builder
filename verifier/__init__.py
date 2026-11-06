"""Deterministic verifier entry points for the archive manifest builder."""

import json
from pathlib import Path

from contract import (
    ArchiveManifestOutput,
    ReadArchiveRequestOutput,
    Task,
    Tool,
)

from .rules import (
    collect_available_files,
    validate_archive_input,
    validate_manifest_entries,
)
from .task import verify_task as verify_build_archive_manifest


def result(valid, message, *, score=None, **details):
    """Return a NanoAgent v0001 verifier result."""

    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def serialize_report(report: ArchiveManifestOutput) -> dict[str, list[dict[str, object]]]:
    """Convert a manifest to the JSON representation written by the tool."""

    return {
        "entries": [
            {
                "path": entry.path,
                "size": entry.size,
                "sha256": entry.sha256,
            }
            for entry in report.entries
        ]
    }


def verify_input(tool, value):
    """Validate tool inputs against the deterministic task evaluation."""

    selected_tool = Tool(tool)
    try:
        validate_archive_input(value.task)
        if selected_tool is Tool.READ_ARCHIVE_REQUEST:
            return result(True, "The archive request is valid.")
        validate_manifest_entries(value.entries)
    except ValueError as error:
        return result(False, "The tool input is invalid.", errors=[str(error)])

    return result(True, "The submitted manifest is structurally valid.")


def verify_output(tool, input_value, output_value, workspace):
    """Validate that each tool returns the value specified by its contract."""

    if Tool(tool) is Tool.READ_ARCHIVE_REQUEST:
        try:
            expected = ReadArchiveRequestOutput(
                fixture_directory=input_value.task.fixture_directory,
                include_patterns=input_value.task.include_patterns,
                exclude_patterns=input_value.task.exclude_patterns,
                available_files=collect_available_files(input_value.task, Path(workspace)),
            )
        except ValueError as error:
            return result(False, "The archive request is invalid.", errors=[str(error)])

        valid = output_value == expected
        return result(
            valid,
            "The archive request was read correctly."
            if valid
            else "The archive request output did not match the fixture directory.",
        )

    expected = ArchiveManifestOutput(entries=input_value.entries)
    expected_report = serialize_report(expected)
    report_file = Path(workspace) / "archive-manifest.json"

    try:
        written_report = json.loads(report_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return result(
            False,
            "The archive manifest was not written.",
            errors=["archive-manifest.json is missing."],
        )
    except json.JSONDecodeError as error:
        return result(
            False,
            "The archive manifest is not valid JSON.",
            errors=[f"archive-manifest.json could not be decoded: {error.msg}."],
        )

    valid = (
        output_value.report_path == "archive-manifest.json"
        and output_value.report == expected
        and written_report == expected_report
    )
    return result(
        valid,
        "The archive manifest was written correctly."
        if valid
        else "The written archive manifest did not match the submitted entries.",
        errors=[]
        if valid
        else ["archive-manifest.json or the returned report differs from the submitted entries."],
    )


def verify_task(task, arguments, output, reference, workspace):
    """Verify final task output against the independently built manifest."""

    verdict = verify_build_archive_manifest(arguments, output, reference, Path(workspace))
    return result(
        verdict.ok,
        verdict.message,
        score=verdict.score,
        errors=verdict.errors,
        task=Task(task).value,
    )
