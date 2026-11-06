import hashlib
import json
from pathlib import Path

import pytest

from contract import ArchiveFile, ArchiveManifestInput
from verifier.rules import (
    build_manifest,
    collect_available_files,
    is_selected,
    path_matches,
    validate_archive_input,
    validate_manifest_entries,
)


def make_task(
    *,
    fixture_directory: str = "fixture",
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> ArchiveManifestInput:
    return ArchiveManifestInput(
        fixture_directory=fixture_directory,
        include_patterns=[] if include_patterns is None else include_patterns,
        exclude_patterns=[] if exclude_patterns is None else exclude_patterns,
    )


def make_fixture(workspace: Path) -> Path:
    fixture = workspace / "fixture"
    (fixture / "docs").mkdir(parents=True)
    (fixture / "src").mkdir()
    (fixture / "empty.txt").write_bytes(b"")
    (fixture / "docs" / "guide.txt").write_bytes(b"guide\n")
    (fixture / "src" / "app.py").write_bytes(b"print('hello')\n")
    (fixture / "src" / "app.tmp").write_bytes(b"temporary\n")
    (fixture / "data.bin").write_bytes(b"\x00\xff\x10")
    return fixture


@pytest.mark.parametrize(
    ("path", "pattern", "matches"),
    [
        ("readme.txt", "*.txt", True),
        ("docs/readme.txt", "*.txt", False),
        ("docs/readme.txt", "**/*.txt", True),
        ("readme.txt", "**/*.txt", True),
        ("src/app.py", "src/*.py", True),
        ("src/nested/app.py", "src/*.py", False),
        ("src/a.py", "src/?.py", True),
        ("src/ab.py", "src/?.py", False),
        ("assets/logo.bin", "**", True),
    ],
)
def test_path_matches_documented_globs(
    path: str,
    pattern: str,
    matches: bool,
) -> None:
    assert path_matches(path, pattern) is matches


def test_excludes_win_after_includes() -> None:
    assert is_selected("src/app.py", ["**/*.py"], ["tests/**"]) is True
    assert is_selected("tests/test_app.py", ["**/*.py"], ["tests/**"]) is False
    assert is_selected("README.md", [], ["**/*.tmp"]) is True


def test_collect_available_files_reports_raw_byte_metadata(tmp_path: Path) -> None:
    make_fixture(tmp_path)

    files = collect_available_files(make_task(), tmp_path)

    assert [file.path for file in files] == [
        "data.bin",
        "docs/guide.txt",
        "empty.txt",
        "src/app.py",
        "src/app.tmp",
    ]
    binary = files[0]
    assert binary.size == 3
    assert binary.sha256 == hashlib.sha256(b"\x00\xff\x10").hexdigest()


def test_build_manifest_applies_patterns_and_sorts_paths(tmp_path: Path) -> None:
    make_fixture(tmp_path)
    task = make_task(
        include_patterns=["**/*.txt", "src/**"],
        exclude_patterns=["**/*.tmp"],
    )

    entries = build_manifest(task, tmp_path)

    assert [entry.path for entry in entries] == [
        "docs/guide.txt",
        "empty.txt",
        "src/app.py",
    ]


def test_repository_fixture_matches_expected_manifest() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    input_data = json.loads(
        (fixtures / "basic-case-input.json").read_text(encoding="utf-8")
    )
    expected_data = json.loads(
        (fixtures / "basic-case-expected.json").read_text(encoding="utf-8")
    )
    task = ArchiveManifestInput(**input_data)

    actual = build_manifest(task, fixtures)

    assert [
        {"path": entry.path, "size": entry.size, "sha256": entry.sha256}
        for entry in actual
    ] == expected_data["entries"]


def test_empty_include_patterns_select_all_regular_files(tmp_path: Path) -> None:
    make_fixture(tmp_path)

    entries = build_manifest(make_task(exclude_patterns=["**/*.tmp"]), tmp_path)

    assert [entry.path for entry in entries] == [
        "data.bin",
        "docs/guide.txt",
        "empty.txt",
        "src/app.py",
    ]


def test_collect_available_files_skips_symlinks(tmp_path: Path) -> None:
    fixture = make_fixture(tmp_path)
    (fixture / "linked-file").symlink_to(fixture / "data.bin")
    (fixture / "linked-directory").symlink_to(fixture / "docs", target_is_directory=True)

    paths = [file.path for file in collect_available_files(make_task(), tmp_path)]

    assert "linked-file" not in paths
    assert all(not path.startswith("linked-directory/") for path in paths)


@pytest.mark.parametrize(
    ("task", "message"),
    [
        (make_task(fixture_directory="../outside"), "normalized relative path"),
        (make_task(fixture_directory="/absolute"), "normalized relative path"),
        (make_task(include_patterns=[""]), "non-empty string"),
        (make_task(include_patterns=["../*.txt"]), "must not contain"),
        (make_task(exclude_patterns=["src\\*.py"]), "must use '/' separators"),
    ],
)
def test_validate_archive_input_rejects_unsafe_values(
    task: ArchiveManifestInput,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_archive_input(task)


def test_collect_available_files_rejects_missing_fixture(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        collect_available_files(make_task(), tmp_path)


def test_collect_available_files_rejects_symlinked_fixture_root(
    tmp_path: Path,
) -> None:
    (tmp_path / "actual").mkdir()
    (tmp_path / "fixture").symlink_to(tmp_path / "actual", target_is_directory=True)

    with pytest.raises(ValueError, match="must not traverse symlinks"):
        collect_available_files(make_task(), tmp_path)


def test_validate_manifest_entries_rejects_duplicates_and_invalid_metadata() -> None:
    valid_hash = "0" * 64

    with pytest.raises(ValueError, match="duplicate path"):
        validate_manifest_entries(
            [
                ArchiveFile("same.txt", 1, valid_hash),
                ArchiveFile("same.txt", 1, valid_hash),
            ]
        )
    with pytest.raises(ValueError, match="non-negative integer"):
        validate_manifest_entries([ArchiveFile("file.txt", -1, valid_hash)])
    with pytest.raises(ValueError, match="lowercase 64-character"):
        validate_manifest_entries([ArchiveFile("file.txt", 1, "NOT-A-HASH")])
