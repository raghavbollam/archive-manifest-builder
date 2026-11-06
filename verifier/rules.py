"""Deterministically inspect fixture files and apply documented path globs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

from contract import ArchiveFile, ArchiveManifestInput

REPORT_NAME = "archive-manifest.json"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _validate_relative_path(path: str, *, label: str) -> PurePosixPath:
    if not isinstance(path, str) or not path:
        raise ValueError(f"{label} must be a non-empty string.")
    if "\\" in path:
        raise ValueError(f"{label} must use '/' separators.")

    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or any(part in {"", ".", ".."} for part in pure_path.parts):
        raise ValueError(f"{label} must be a normalized relative path.")
    if str(pure_path) != path:
        raise ValueError(f"{label} must be a normalized relative path.")
    return pure_path


def _validate_pattern(pattern: str, *, label: str) -> None:
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{label} must be a non-empty string.")
    if "\\" in pattern:
        raise ValueError(f"{label} must use '/' separators.")
    if pattern.startswith("/") or pattern.endswith("/") or "//" in pattern:
        raise ValueError(f"{label} must be a normalized file pattern.")
    if any(part in {".", ".."} for part in pattern.split("/")):
        raise ValueError(f"{label} must not contain '.' or '..' path segments.")


def validate_archive_input(task: ArchiveManifestInput) -> None:
    """Raise ValueError unless an archive request is safe and well formed."""

    _validate_relative_path(task.fixture_directory, label="fixture_directory")

    for index, pattern in enumerate(task.include_patterns):
        _validate_pattern(pattern, label=f"include_patterns[{index}]")
    for index, pattern in enumerate(task.exclude_patterns):
        _validate_pattern(pattern, label=f"exclude_patterns[{index}]")


def _glob_regex(pattern: str) -> re.Pattern[str]:
    pieces: list[str] = ["^"]
    index = 0

    while index < len(pattern):
        character = pattern[index]
        if character == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    pieces.append("(?:.*/)?")
                    index += 1
                else:
                    pieces.append(".*")
                continue
            pieces.append("[^/]*")
        elif character == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(character))
        index += 1

    pieces.append("$")
    return re.compile("".join(pieces))


def path_matches(path: str, pattern: str) -> bool:
    """Return whether one normalized path matches one documented glob."""

    _validate_relative_path(path, label="path")
    _validate_pattern(pattern, label="pattern")
    return _glob_regex(pattern).fullmatch(path) is not None


def is_selected(
    path: str,
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> bool:
    """Apply includes followed by winning excludes to one path."""

    included = not include_patterns or any(
        path_matches(path, pattern) for pattern in include_patterns
    )
    excluded = any(path_matches(path, pattern) for pattern in exclude_patterns)
    return included and not excluded


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fixture_root(task: ArchiveManifestInput, workspace: Path) -> tuple[Path, Path]:
    validate_archive_input(task)

    workspace_root = Path(workspace).resolve()
    fixture_path = workspace_root
    for part in PurePosixPath(task.fixture_directory).parts:
        fixture_path /= part
        if fixture_path.is_symlink():
            raise ValueError("fixture_directory must not traverse symlinks.")

    fixture_root = fixture_path.resolve()

    if not fixture_root.is_relative_to(workspace_root):
        raise ValueError("fixture_directory must stay within the workspace.")
    if not fixture_root.exists():
        raise ValueError(f"fixture_directory does not exist: {task.fixture_directory!r}.")
    if not fixture_root.is_dir():
        raise ValueError(f"fixture_directory is not a directory: {task.fixture_directory!r}.")

    return workspace_root, fixture_root


def collect_available_files(
    task: ArchiveManifestInput,
    workspace: Path,
) -> list[ArchiveFile]:
    """Return metadata for every regular non-symlink file in the fixture tree."""

    workspace_root, fixture_root = _fixture_root(task, workspace)
    report_path = workspace_root / REPORT_NAME
    files: list[ArchiveFile] = []

    def visit(directory: Path) -> None:
        for file_path in sorted(directory.iterdir(), key=lambda path: path.name):
            if file_path.is_symlink() or not file_path.is_file():
                if file_path.is_dir() and not file_path.is_symlink():
                    visit(file_path)
                continue

            resolved_file = file_path.resolve()
            if not resolved_file.is_relative_to(fixture_root):
                continue
            if resolved_file == report_path:
                continue

            relative_path = resolved_file.relative_to(fixture_root).as_posix()
            _validate_relative_path(relative_path, label="fixture file path")
            files.append(
                ArchiveFile(
                    path=relative_path,
                    size=resolved_file.stat().st_size,
                    sha256=_sha256(resolved_file),
                )
            )

    visit(fixture_root)
    return sorted(files, key=lambda file: file.path)


def build_manifest(
    task: ArchiveManifestInput,
    workspace: Path,
) -> list[ArchiveFile]:
    """Build the canonical selected manifest for one archive request."""

    return [
        file
        for file in collect_available_files(task, workspace)
        if is_selected(file.path, task.include_patterns, task.exclude_patterns)
    ]


def validate_manifest_entries(entries: list[ArchiveFile]) -> None:
    """Raise ValueError unless submitted entries are normalized and canonical."""

    seen_paths: set[str] = set()
    previous_path: str | None = None

    for index, entry in enumerate(entries):
        _validate_relative_path(entry.path, label=f"entries[{index}].path")
        if entry.path in seen_paths:
            raise ValueError(f"entries contains duplicate path {entry.path!r}.")
        if previous_path is not None and entry.path <= previous_path:
            raise ValueError("entries must be sorted by path in ascending lexical order.")
        if isinstance(entry.size, bool) or not isinstance(entry.size, int) or entry.size < 0:
            raise ValueError(f"entries[{index}].size must be a non-negative integer.")
        if not isinstance(entry.sha256, str) or SHA256_PATTERN.fullmatch(entry.sha256) is None:
            raise ValueError(
                f"entries[{index}].sha256 must be a lowercase 64-character hexadecimal digest."
            )

        seen_paths.add(entry.path)
        previous_path = entry.path
