"""Verify an agent's submitted archive manifest deterministically."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contract import ArchiveFile, ArchiveManifestInput, ArchiveManifestOutput

from .rules import build_manifest, validate_manifest_entries


@dataclass(frozen=True)
class VerificationResult:
    """The deterministic verdict for one submitted task answer."""

    ok: bool
    score: float
    message: str
    errors: list[str]


def _describe(entry: ArchiveFile) -> str:
    return f"path={entry.path!r}, size={entry.size}, sha256={entry.sha256!r}"


def verify_task(
    arguments: ArchiveManifestInput,
    output: ArchiveManifestOutput,
    reference: object | None,
    workspace: Path,
) -> VerificationResult:
    """Compare a submitted manifest with an independent filesystem walk."""

    del reference

    try:
        expected = build_manifest(arguments, Path(workspace))
        validate_manifest_entries(output.entries)
    except ValueError as error:
        return VerificationResult(
            ok=False,
            score=0.0,
            message="The archive request or submitted manifest is invalid.",
            errors=[str(error)],
        )

    errors: list[str] = []
    expected_by_path = {entry.path: entry for entry in expected}
    actual_by_path = {entry.path: entry for entry in output.entries}

    for path in expected_by_path.keys() - actual_by_path.keys():
        errors.append(f"Missing manifest entry for {path!r}.")
    for path in actual_by_path.keys() - expected_by_path.keys():
        errors.append(f"Unexpected manifest entry for {path!r}.")

    for path in expected_by_path.keys() & actual_by_path.keys():
        expected_entry = expected_by_path[path]
        actual_entry = actual_by_path[path]
        if actual_entry != expected_entry:
            errors.append(
                f"Manifest entry for {path!r} does not match. "
                f"Expected ({_describe(expected_entry)}); "
                f"received ({_describe(actual_entry)})."
            )

    expected_paths = [entry.path for entry in expected]
    actual_paths = [entry.path for entry in output.entries]
    if not errors and actual_paths != expected_paths:
        errors.append(
            f"Manifest paths are not in canonical order. Expected {expected_paths!r}."
        )

    if errors:
        return VerificationResult(
            ok=False,
            score=0.0,
            message="The submitted manifest did not match the fixture directory.",
            errors=sorted(errors),
        )

    return VerificationResult(
        ok=True,
        score=1.0,
        message="Every manifest entry matches the selected fixture files.",
        errors=[],
    )
